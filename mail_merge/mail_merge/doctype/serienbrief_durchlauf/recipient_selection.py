"""Permission-aware recipient selection shared by the picker and bulk add."""

import frappe
from frappe import _
from frappe.utils import cint, cstr


def iteration_doctype(doc):
	return cstr(doc.iteration_doctype or "").strip() or cstr(
		frappe.db.get_value("Serienbrief Vorlage", doc.vorlage, "haupt_verteil_objekt") if doc.vorlage else ""
	).strip()


def existing_recipients(doc, doctype):
	return {
		row.objekt for row in doc.get("iteration_objekte") or []
		if (row.iteration_doctype or doctype) == doctype and row.objekt
	}


def _selection_scope(doctype, filters):
	for hook in frappe.get_hooks("mail_merge_recipient_scope"):
		scope = frappe.get_attr(hook)(doctype, filters)
		if scope is not None:
			return scope
	if filters:
		frappe.throw(_("Für diesen Iterations-Doctype stehen keine Objektfilter zur Verfügung."))
	return {}


def _readable_recipients(doctype, query, scope):
	meta = frappe.get_meta(doctype)
	title = meta.get_title_field()
	fields = list(dict.fromkeys(["name", *([title] if title else []), *scope.get("fields", [])]))
	search = [[field, "like", f"%{query}%"] for field in dict.fromkeys(["name", title or "name"])] if query else None
	accept = scope.get("accept")
	# Providers with virtual links can defer User Permission rules to the
	# full document permission check below. Other list restrictions still apply.
	list_options = {"ignore_user_permissions": True} if scope.get("check_user_permissions_per_document") else {}
	start = 0
	while True:
		rows = frappe.get_list(
			doctype, fields=fields, filters=scope.get("filters"), or_filters=search,
			order_by="name asc", limit_start=start, limit_page_length=250, **list_options,
		)
		for row in rows:
			if (accept is None or accept(row)) and frappe.has_permission(doctype, "read", doc=row.name):
				yield row, cstr(row.get(title) or row.name)
		if len(rows) < 250:
			break
		start += len(rows)


def find_recipients(doc, *, query=None, filters=None, sort="name_asc", offset=0, limit=25, bulk=False):
	doctype = iteration_doctype(doc)
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if filters is not None and not isinstance(filters, dict):
		frappe.throw(_("Ungültige Empfängerfilter."))
	if not doctype or not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		if bulk:
			raise frappe.PermissionError
		return {"doctype": doctype, "items": [], "total": 0}

	query = cstr(query).strip()
	scope = _selection_scope(doctype, filters or {})
	if bulk and not scope.get("label"):
		frappe.throw(_("Bitte wählen Sie eine Immobilie oder einen Gebäudeteil."))

	existing = existing_recipients(doc, doctype)
	items = []
	skipped = 0
	locations = scope.get("locations", {})
	for row, label in _readable_recipients(doctype, query, scope):
		if row.name in existing:
			skipped += 1
			continue
		location = locations.get(row.get(scope.get("location_key") or "name"), ())
		items.append({"id": row.name, "label": label, "location": location})

	if bulk:
		return items, skipped

	# Display titles can fall back to the ID. Sort the complete result by that
	# effective title (or the linked unit's location), then take the requested page.
	items.sort(key=lambda item: (item["id"].casefold(), item["id"]))
	if sort in ("location_asc", "location_desc") and scope.get("options"):
		key = lambda item: tuple(part.casefold() for part in item["location"]) or ("", "", "")
	else:
		key = lambda item: item["label"].casefold()
	items.sort(key=key, reverse=sort in ("name_desc", "location_desc"))
	offset = max(cint(offset), 0)
	limit = min(max(cint(limit) or 25, 1), 100)
	return {
		"doctype": doctype,
		"items": items[offset:offset + limit],
		"total": len(items),
		"scope": scope.get("options"),
		"scope_label": scope.get("label"),
	}
