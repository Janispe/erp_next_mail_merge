"""Prototype: choose a template, fill letters, preview, then save the exact PDFs."""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import time
import uuid
from datetime import date
from io import BytesIO

import frappe
from frappe import _
from frappe.utils import nowdate

from mail_merge.mail_merge.utils.letter_composer_state import (
	input_fingerprint,
)

TTL = 1800
MAX_RECIPIENTS = 10
SCALAR_TYPES = {"Text", "String", "Datum", "Bool", "Zahl"}


def core():
	from mail_merge.mail_merge.doctype.serienbrief_durchlauf import serienbrief_durchlauf

	return serienbrief_durchlauf


def read(doctype, name):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return doc


def can_create():
	for dt in ("Serienbrief Durchlauf", "Serienbrief Dokument"):
		if not frappe.has_permission(dt, "create") or not frappe.has_permission(dt, "read"):
			raise frappe.PermissionError


def template_snapshot(name):
	template = read("Serienbrief Vorlage", name)
	blocks, seen = [], set()
	queue = [r.baustein for r in template.get("textbausteine") or [] if r.baustein]
	queue += core()._extract_inline_block_names(core()._get_template_template_source(template))
	while queue:
		key = queue.pop(0)
		if key in seen:
			continue
		seen.add(key)
		if len(seen) > 100:
			frappe.throw(_("Zu viele Textbausteine."))
		block = read("Serienbrief Textbaustein", key)
		fixed = core().fixed_version_number(template, key)
		if fixed:
			# Fixierte Version: gerendert wird der unveraenderliche Snapshot, nicht der aktuelle Stand.
			block = core().get_textbaustein(key, template=template)
		blocks.append({"baustein": key, "fixierte_version": fixed} if fixed else block.as_dict())
		queue += core()._extract_inline_block_names(core()._get_textbaustein_template_source(block))
	revision = hashlib.sha256(
		json.dumps([template.as_dict(), blocks], sort_keys=True, default=str).encode()
	).hexdigest()
	return template, revision


def fields_for(template):
	from mail_merge.mail_merge.utils.render_inputs import input_fields
	return input_fields(template)


@frappe.whitelist()
def describe_template(template):
	can_create()
	doc, revision = template_snapshot(template)
	return {
		"name": doc.name,
		"title": doc.title,
		"description": doc.get("description") or "",
		"recipient_doctype": doc.haupt_verteil_objekt,
		"revision": revision,
		"fields": fields_for(doc),
		"max_recipients": MAX_RECIPIENTS,
	}


@frappe.whitelist()
def search_recipients(template, query="", offset=0):
	doc = read("Serienbrief Vorlage", template)
	dt = doc.haupt_verteil_objekt
	if not frappe.has_permission(dt, "read"):
		raise frappe.PermissionError
	title_field = frappe.get_meta(dt).get_title_field()
	fields = ["name"] + ([title_field] if title_field and title_field != "name" else [])
	filters = [["name", "like", f"%{query}%"]]
	if title_field and title_field != "name":
		filters.append([title_field, "like", f"%{query}%"])
	rows = frappe.get_list(
		dt,
		fields=fields,
		or_filters=filters if query else None,
		limit_start=max(0, int(offset)),
		limit_page_length=21,
		order_by="name asc",
	)
	return {
		"items": [{"id": r.name, "label": r.get(title_field) or r.name} for r in rows[:20]],
		"has_more": len(rows) > 20,
	}


def text_value(value):
	if not isinstance(value, str) or len(value) > 4000:
		raise ValueError("Bitte höchstens 4.000 Zeichen eingeben.")
	if re.search(r"\{[\{%#]|[<>]", html.unescape(value)):
		raise ValueError("Bitte nur Text eingeben, ohne HTML oder Vorlagencode.")
	return value


def validate_value(value, field):
	if value is None or (isinstance(value, str) and not value.strip()):
		if field["required"]:
			raise ValueError(f"{field['label']} fehlt.")
		return ""
	kind = field["type"]
	if kind == "Zahl":
		if type(value) not in (int, float) or not math.isfinite(value):
			raise ValueError("Bitte eine gültige Zahl eingeben.")
	elif kind == "Bool":
		if type(value) is not bool:
			raise ValueError("Bitte Ja oder Nein auswählen.")
	elif kind == "Datum":
		try:
			if date.fromisoformat(value).isoformat() != value:
				raise ValueError()
		except (TypeError, ValueError):
			raise ValueError("Bitte ein gültiges Datum eingeben.") from None
	else:
		text_value(value)
		value = html.escape(value, quote=True)
	return value


def cache_key(token):
	if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{32}", token):
		frappe.throw(_("Ungültige Vorschau."))
	return f"letter-composer:{frappe.session.user}:{token}"


def prepared(token):
	data = frappe.cache.get_value(cache_key(token))
	if not data or data["expires"] <= time.time():
		frappe.throw(_("Die Vorschau ist abgelaufen. Bitte erneut prüfen."))
	return data


@frappe.whitelist(methods=["POST"])
def preview(payload):
	can_create()
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	if not isinstance(data, dict):
		frappe.throw(_("Ungültige Briefangaben."))
	template, revision = template_snapshot(data.get("template"))
	if revision != data.get("revision"):
		frappe.throw(_("Die Vorlage wurde geändert. Bitte die Vorlage neu auswählen."))
	names = data.get("recipients") or []
	if (
		not isinstance(names, list)
		or not 1 <= len(names) <= MAX_RECIPIENTS
		or any(not isinstance(n, str) for n in names)
		or len(set(names)) != len(names)
	):
		frappe.throw(_("Bitte 1 bis 10 unterschiedliche Empfänger auswählen."))
	targets = [read(template.haupt_verteil_objekt, n) for n in names]
	fields = fields_for(template)
	allowed = {field["name"] for field in fields}
	values, individual = data.get("values") or {}, data.get("individual") or {}
	if (
		not isinstance(values, dict)
		or set(values) - allowed
		or not isinstance(individual, dict)
		or set(individual) - set(names)
	):
		frappe.throw(_("Unbekannte Eingabefelder oder Empfänger."))
	for entry in individual.values():
		if (
			not isinstance(entry, dict)
			or not isinstance(entry.get("values", {}), dict)
			or set(entry.get("values") or {}) - allowed
		):
			frappe.throw(_("Unbekannte individuelle Eingabefelder."))
	if data.get("addition") or any(entry.get("addition") for entry in individual.values()):
		frappe.throw(_("Zusatztexte werden jetzt über Vorlagenvariablen ausgefüllt. Bitte die Seite neu laden."))
	letter_date = data.get("date") or nowdate()
	try:
		if date.fromisoformat(letter_date).isoformat() != letter_date:
			raise ValueError()
	except (TypeError, ValueError):
		frappe.throw(_("Ungültiges Briefdatum."))
	token = uuid.uuid4().hex
	run = frappe.get_doc(
		{
			"doctype": "Serienbrief Durchlauf",
			"name": "SBDL-BRIEF-" + token,
			"title": template.title,
			"vorlage": template.name,
			"kategorie": template.kategorie,
			"date": letter_date,
			"iteration_doctype": template.haupt_verteil_objekt,
			"status": "Läuft",
			"iteration_objekte": [],
		}
	)
	# Keep shared values shared; persist only explicit per-recipient overrides.
	common = {
		k: {"value": html.escape(v, quote=True) if isinstance(v, str) else v}
		for k, v in values.items()
	}
	run.variablen_werte = json.dumps(common)
	outputs, checks = [], []
	for target in targets:
		custom = individual.get(target.name) or {}
		errors, effective, changes = {}, {}, []
		source_row = frappe._dict(_iteration_doc=target)
		source_context = run._build_context(source_row, len(checks) + 1, template=template, total=len(targets), strict_variables=False)
		for field in fields:
			key = field["name"]
			overrides = custom.get("values") or {}
			origin = "individual" if key in overrides else "common" if key in values else "template"
			value = overrides[key] if key in overrides else values.get(key, field["default"])
			if origin == "template" and value is None:
				value = core._resolve_value_path(key, source_context)
			try:
				effective[key] = {"value": validate_value(value, field)}
			except ValueError as exc:
				errors[key] = str(exc)
			changes.append({"label": field["label"], "value": value, "origin": origin})
		run.append(
			"iteration_objekte",
			{
				"iteration_doctype": template.haupt_verteil_objekt,
				"objekt": target.name,
				"variablen_werte": json.dumps(
					{
						k: v
						for k, v in effective.items()
						if k in (custom.get("values") or {})
					}
				),
			},
		)
		check = {
			"recipient": target.name,
			"fields": errors,
			"changes": changes,
			"status": "missing" if errors else "ready",
		}
		checks.append(check)
		if errors:
			continue
		try:
			row = run._build_target_row_from_iteration(run.iteration_objekte[-1])
			context = run._build_context(row, len(checks), template=template, total=len(targets))
			segments = run._render_template_content(template, context)
			if not segments:
				raise ValueError("Die Vorlage erzeugt für diesen Empfänger keinen Brief.")
			footer = frappe._dict(
				vorlage=template.name,
				iteration_doctype=run.iteration_doctype,
				objekt=target.name,
				date=letter_date,
				variablen_werte=json.dumps({**common, **effective}),
			)
			pdf = run._render_segments_pdf_bytes(segments, footer_doc=footer)
			from pypdf import PdfReader

			reader = PdfReader(BytesIO(pdf))
			if not reader.pages:
				raise ValueError("Die Vorschau enthält keine PDF-Seiten.")
			body = run._wrap_html_fragment("".join(run._render_segments_preview_pages(segments)))
			check.update(
				html=body,
				pages=len(reader.pages),
				pdf_url=f"/api/method/mail_merge.mail_merge.utils.letter_composer.preview_pdf?token={token}&index={len(outputs)}",
			)
			outputs.append(
				{
					"recipient": target.name,
					"html": body,
					"pdf": pdf,
					"values": json.dumps({**common, **effective}),
					"pages": len(reader.pages),
				}
			)
		except Exception as exc:
			message = re.split(r"<pre|Traceback|Vorlagen-Zeile", str(exc), maxsplit=1)[0]
			check.update(
				status="error", message=html.unescape(re.sub(r"<[^>]*>", "", message))[:800]
			)
	if sum(len(o["pdf"]) for o in outputs) > 10 * 1024 * 1024:
		frappe.throw(_("Die Vorschau ist zu groß. Bitte weniger Empfänger auswählen."))
	ready = all(c["status"] == "ready" for c in checks)
	snapshot = {
		"run": run.as_dict(),
		"outputs": outputs,
		"revision": revision,
		"targets": {t.name: str(t.modified) for t in targets},
		"expires": time.time() + TTL,
		"ready": ready,
	}
	frappe.cache.set_value(cache_key(token), snapshot, expires_in_sec=TTL)
	return {"ready": ready, "token": token, "checks": checks, "expires_in_seconds": TTL}


@frappe.whitelist()
def preview_pdf(token, index=0):
	data = prepared(token)
	index = int(index)
	if index < 0 or index >= len(data["outputs"]):
		frappe.throw(_("Vorschau nicht gefunden."))
	frappe.local.response.update(
		type="pdf", filename="brief-vorschau.pdf", filecontent=data["outputs"][index]["pdf"]
	)


@frappe.whitelist(methods=["POST"])
def save(token):
	can_create()
	with frappe.cache.lock(cache_key(token) + ":save", timeout=120, blocking_timeout=5):
		data = prepared(token)
		if not data["ready"]:
			frappe.throw(_("Bitte zuerst alle fehlenden Angaben und Vorschaufehler beheben."))
		name = data["run"]["name"]
		if frappe.db.exists("Serienbrief Durchlauf", name):
			doc = read("Serienbrief Durchlauf", name)
			if doc.owner != frappe.session.user:
				raise frappe.PermissionError
			return {"docname": name, "reused": True}
		template, revision = template_snapshot(data["run"]["vorlage"])
		if revision != data["revision"]:
			frappe.throw(_("Die Vorlage wurde geändert. Bitte die Vorschau aktualisieren."))
		for target, modified in data["targets"].items():
			if str(read(data["run"]["iteration_doctype"], target).modified) != modified:
				frappe.throw(_("Empfängerdaten wurden geändert. Bitte die Vorschau aktualisieren."))
		try:
			run = frappe.get_doc(data["run"])
			run.insert(set_name=name)
			for output in data["outputs"]:
				doc = frappe.get_doc(
					{
						"doctype": "Serienbrief Dokument",
						"durchlauf": name,
						"vorlage": run.vorlage,
						"kategorie": run.kategorie,
						"date": run.date,
						"iteration_doctype": run.iteration_doctype,
						"objekt": output["recipient"],
						"title": output["recipient"],
						"html": output["html"],
						"variablen_werte": output["values"],
						"status": "Generiert",
						"pages": output["pages"],
					}
				).insert()
				file = frappe.get_doc(
					{
						"doctype": "File",
						"file_name": doc.name + ".pdf",
						"is_private": 1,
						"attached_to_doctype": doc.doctype,
						"attached_to_name": doc.name,
						"content": output["pdf"],
					}
				).insert(ignore_permissions=True)
				doc.db_set("generated_pdf_file", file.file_url, update_modified=False)
			run.db_set(
				{
					"status": "Generiert",
					"run_summary": json.dumps(
						{
							"total": len(data["outputs"]),
							"generated": len(data["outputs"]),
							"error": 0,
							"skipped": 0,
							"input_fingerprint": input_fingerprint(run),
							"composer_revision": revision,
						}
					),
				}
			)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			raise
		return {"docname": name}
