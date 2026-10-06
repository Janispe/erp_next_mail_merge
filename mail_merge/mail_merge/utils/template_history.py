"""Reversible presentation groups and permission-filtered evidence for template versions."""

from itertools import pairwise
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, cstr

VERSION = "Serienbrief Vorlagenversion"
TEMPLATE = "Serienbrief Vorlage"
DOCUMENT = "Serienbrief Dokument"
RUN = "Serienbrief Durchlauf"


def _access(template, permission="read"):
	name = cstr(template).strip()
	if not name or not frappe.has_permission(TEMPLATE, permission, doc=name):
		frappe.throw(_("Keine Berechtigung für die Versionshistorie dieser Vorlage."), frappe.PermissionError)
	return name


def _version(template, name):
	from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import (
		_require_template_version,
	)

	return _require_template_version(cstr(name).strip(), template)


def enrich_history(result, template):
	items = result.get("items") or []
	by_name = {item["name"]: item for item in items}
	for item in items:
		item["group_members"] = [v["name"] for v in items if v.get("history_group") == item["name"]]
		item["can_group"] = bool(
			item.get("is_proposal") and not item.get("history_group") and not item["group_members"]
		)
		reasons = []
		if item.get("delete_block_reason"):
			reasons.append(item["delete_block_reason"])
		for other in items:
			if other.get("based_on") == item["name"]:
				reasons.append(_("Version {0} basiert auf dieser Version.").format(other["number"]))
			if other.get("restored_from") == item["name"]:
				reasons.append(
					_("Version {0} wurde aus dieser Version wiederhergestellt.").format(other["number"])
				)
		if item.get("history_group"):
			head = by_name.get(item["history_group"])
			reasons.append(
				_(
					"Zwischenstand der Zusammenfassung bei Version {0}; zunächst die Zusammenfassung auflösen."
				).format(head["number"] if head else "?")
			)
		if item["group_members"]:
			reasons.append(
				_("Diese Version fasst Zwischenstände zusammen; zunächst die Zusammenfassung auflösen.")
			)
		item["delete_block_reasons"] = list(dict.fromkeys(reasons))
		if reasons:
			item["can_delete"] = False
	result["can_manage_history"] = bool(frappe.has_permission(TEMPLATE, "write", doc=template))
	return result


def group_versions(template, versions):
	name = _access(template, "write")
	selected = frappe.parse_json(versions) if isinstance(versions, str) else versions
	if (
		not isinstance(selected, list)
		or not 2 <= len(selected) <= 50
		or any(not isinstance(v, str) or not v for v in selected)
		or len(set(selected)) != len(selected)
	):
		frappe.throw(_("Bitte 2 bis 50 unterschiedliche Vorschlagsversionen auswählen."))
	# Serialize presentation changes per template, including simultaneous ungroup.
	frappe.db.get_value(TEMPLATE, name, "name", for_update=True)
	rows = sorted((_version(name, v) for v in selected), key=lambda v: v.version_number)
	ids = [v.name for v in rows]
	for row in rows:
		if (
			row.source != "KI-Vorschlag"
			or row.get("history_group")
			or frappe.db.exists(VERSION, {"history_group": row.name})
		):
			frappe.throw(_("Nur noch nicht zusammengefasste KI-Vorschläge können zusammengefasst werden."))
	for previous, current in pairwise(rows):
		if current.based_on != previous.name:
			frappe.throw(_("Die Auswahl muss eine lückenlose Vorschlagskette bilden."))
	head = rows[-1].name
	for row in rows[:-1]:
		frappe.db.set_value(VERSION, row.name, "history_group", head, update_modified=False)
	return {"head": head, "members": ids[:-1]}


def ungroup_versions(template, version):
	name = _access(template, "write")
	frappe.db.get_value(TEMPLATE, name, "name", for_update=True)
	head = _version(name, version)
	if head.get("history_group"):
		frappe.throw(_("Bitte die Ergebnisversion der Zusammenfassung auswählen."))
	members = frappe.get_all(VERSION, filters={"vorlage": name, "history_group": head.name}, pluck="name")
	for member in members:
		frappe.db.set_value(VERSION, member, "history_group", None, update_modified=False)
	return {"head": head.name, "members": members}


def _count(doctype, filters):
	rows = frappe.get_list(
		doctype, filters=filters, fields=[{"COUNT": "name", "as": "total"}], limit_page_length=0
	)
	return cint(rows[0].total) if rows else 0


def _pdf_url(row):
	url = cstr(row.get("generated_pdf_file"))
	if not url.startswith(("/files/", "/private/files/")):
		return None
	file_name = frappe.db.get_value(
		"File", {"file_url": url, "attached_to_doctype": DOCUMENT, "attached_to_name": row.name}, "name"
	)
	if file_name and frappe.has_permission("File", "read", doc=file_name):
		return url
	return None


def version_usage(template, version=None, *, include_group=1, kind="documents", offset=0, limit=20):
	name = _access(template)
	if kind not in {"documents", "runs"}:
		frappe.throw(_("Unbekannte Art der Verknüpfung."))
	offset, limit = max(0, cint(offset)), min(100, max(1, cint(limit)))
	filters = {"vorlage": name}
	version_names = []
	if version:
		chosen = _version(name, version)
		version_names = [chosen.name]
		if cint(include_group) and not chosen.get("history_group"):
			version_names += frappe.get_all(
				VERSION, filters={"vorlage": name, "history_group": chosen.name}, pluck="name"
			)
		filters["vorlagenversion"] = ["in", version_names]
	counts = {}
	for key, doctype in (("documents", DOCUMENT), ("runs", RUN)):
		counts[key] = _count(doctype, filters) if frappe.has_permission(doctype, "read") else 0
	doctype = DOCUMENT if kind == "documents" else RUN
	rows = []
	if frappe.has_permission(doctype, "read"):
		fields = ["name", "title", "date", "status", "docstatus", "vorlagenversion"]
		fields += (
			["durchlauf", "iteration_doctype", "objekt", "generated_pdf_file"]
			if kind == "documents"
			else ["iteration_doctype"]
		)
		rows = frappe.get_list(
			doctype,
			filters=filters,
			fields=fields,
			order_by="creation desc, name desc",
			limit_start=offset,
			limit_page_length=limit,
		)
	versions = frappe.get_all(VERSION, filters={"vorlage": name}, fields=["name", "version_number"])
	numbers = {v.name: v.version_number for v in versions}
	items = []
	for row in rows:
		item = dict(row)
		item["version_number"] = numbers.get(row.vorlagenversion)
		item["url"] = (
			f"/desk/{'serienbrief-dokument' if kind == 'documents' else 'serienbrief-durchlauf'}/{quote(row.name, safe='')}"
		)
		item["pdf_url"] = _pdf_url(row) if kind == "documents" else None
		item.pop("generated_pdf_file", None)
		items.append(item)
	return {
		"items": items,
		"counts": counts,
		"kind": kind,
		"offset": offset,
		"limit": limit,
		"total": counts[kind],
		"has_more": offset + len(items) < counts[kind],
		"versions": version_names,
	}
