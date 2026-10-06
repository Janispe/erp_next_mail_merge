"""Separate open preview inputs, recipient data and template errors before PDF generation."""

import html
import math
import re
from datetime import date

import frappe

from mail_merge.mail_merge.utils.render_diagnostics import exception_chain, render_diagnostic


class PreviewInputError(ValueError):
	def __init__(self, issues, *, invalid=False):
		super().__init__("Vorschau-Eingaben fehlen oder sind ungültig.")
		self.issues = issues
		self.invalid = invalid


def preview_inputs(doc):
	from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import _parse_variable_values

	mapping = _parse_variable_values(doc.get("variablen_werte"))
	paths = frappe.parse_json(doc.get("pfad_zuordnung") or "{}") or {}
	return [{"field": frappe.scrub(row.variable), "label": row.label or row.variable,
		"type": row.variable_type or "Text", "required": not bool(row.get("optional")),
		"reference_doctype": row.get("reference_doctype") or "",
		"fillable": not bool((mapping.get(frappe.scrub(row.variable)) or {}).get("path") or (paths.get(frappe.scrub(row.variable)) if row.variable_type in {"Doctype", "Doctype Liste"} else None)),
		"path": (mapping.get(frappe.scrub(row.variable)) or {}).get("path") or (paths.get(frappe.scrub(row.variable)) if row.variable_type in {"Doctype", "Doctype Liste"} else None),
		"source": "input"} for row in doc.get("variables") or [] if row.variable]


def require_preview_inputs(doc, context):
	issues = []
	for field in preview_inputs(doc):
		value = context.get(field["field"])
		if field["required"] and (value is None or isinstance(value, str) and not value.strip()):
			issue = dict(field)
			if not field["fillable"]:
				issue.update(source="recipient_data", path=field["path"])
			issues.append(issue)
	if issues:
		raise PreviewInputError(issues)


def apply_preview_values(doc, raw):
	"""Transient declared inputs only; never save the document or change definitions."""
	if raw is None:
		return
	try:
		values = frappe.parse_json(raw) if isinstance(raw, str) else raw
	except (ValueError, TypeError):
		raise PreviewInputError([], invalid=True) from None
	fields = {field["field"]: field for field in preview_inputs(doc) if field["fillable"]}
	if not isinstance(values, dict) or set(values) - fields.keys():
		raise PreviewInputError([], invalid=True)
	mapping = frappe.parse_json(doc.get("variablen_werte") or "{}") or {}
	for key, value in values.items():
		if value is None or value == "":
			continue
		field = fields[key]
		kind = field["type"]
		valid = False
		if kind == "Bool":
			valid = type(value) is bool or isinstance(value, str) and value.lower() in {"true", "false", "0", "1"}
		elif kind == "Zahl":
			valid = type(value) in (int, float) and math.isfinite(value)
		elif kind == "Datum":
			try:
				valid = isinstance(value, str) and date.fromisoformat(value).isoformat() == value
			except ValueError:
				pass
		elif kind == "Doctype Liste":
			valid = isinstance(value, list) and 1 <= len(value) <= 20 and all(isinstance(v, str) and v.strip() for v in value)
		else:
			valid = isinstance(value, str) and len(value) <= 5000
		if isinstance(value, str) and re.search(r"[<>]|\{[\{%#]", value):
			valid = False
		if not valid:
			raise PreviewInputError([field], invalid=True)
		mapping[key] = {"value": value}
	doc.variablen_werte = frappe.as_json(mapping)


def preview_error(exc, doc, *, phase="render"):
	from jinja2.exceptions import UndefinedError

	chain = exception_chain(exc)
	input_error = next((e for e in chain if isinstance(e, PreviewInputError)), None)
	if input_error:
		data_problem = any(issue["source"] == "recipient_data" for issue in input_error.issues)
		return {"code": "INVALID_INPUT" if input_error.invalid else "MISSING_DATA" if data_problem else "MISSING_INPUT",
			"message": "Bitte die Vorschauwerte prüfen." if input_error.invalid else "Für die Vorschau fehlen Daten aus dem Zielobjekt." if data_problem else "Für die Vorschau fehlen noch Eingabewerte.",
			"action": "correct_inputs" if input_error.invalid else "check_recipient_data" if data_problem else "provide_inputs",
			"issues": input_error.issues}
	# Known renderer messages include source excerpts; discard those first.
	for cause in chain:
		raw = re.sub(r"<pre\b[^>]*>.*?</pre>", "", str(cause), flags=re.DOTALL | re.IGNORECASE)
		raw = re.split(r"Vorlagen-Zeile|Kandidaten in dieser Zeile|Traceback", raw, maxsplit=1)[0]
		text = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
		mapped = re.search(r"Pfad\s+([\w.\[\]]+)\s+für Variable\s+(\w+)\s+.*?konnte nicht aufgelöst werden", text)
		placeholder = re.search(r"Platzhalter\s+\{\{?\s*\$\s*([\w.\[\]]+)\s*\$\s*\}\}?\s+konnte nicht aufgelöst werden", text)
		if mapped or placeholder:
			path = (mapped or placeholder)[1]
			field = next((f for f in preview_inputs(doc) if mapped and f["field"] == mapped[2]), {})
			is_data = path.startswith("objekt.") or path == "__self__"
			return {"code": "MISSING_DATA" if is_data else "UNRESOLVED_PATH",
				"message": "Ein zugeordneter Datenpfad konnte nicht aufgelöst werden.",
				"action": "check_recipient_data" if is_data else "review_template",
				"issues": [{**field, "field": field.get("field") or path.rsplit(".", 1)[-1], "path": path, "source": "recipient_data" if is_data else "template"}],
				"diagnostic": render_diagnostic(exc, phase=phase)}
		missing_field = re.search(r"Feld\s+(\w+)\s+(existiert nicht im DocType|kann nicht gelesen werden)", text)
		if missing_field:
			is_data = missing_field[2] == "kann nicht gelesen werden"
			return {"code": "MISSING_DATA" if is_data else "INVALID_TEMPLATE_FIELD",
				"message": f"Feld {missing_field[1]} ist über die Vorlage nicht lesbar.",
				"action": "check_recipient_data" if is_data else "review_template",
				"issues": [{"field": missing_field[1], "source": "recipient_data" if is_data else "template"}],
				"diagnostic": render_diagnostic(exc, phase=phase)}
	root = chain[-1]
	diagnostic = render_diagnostic(exc, phase=phase)
	result = {"code": "RENDER_FAILED", "message": diagnostic["message"], "action": "review_template", "issues": [], "diagnostic": diagnostic}
	if isinstance(root, UndefinedError):
		match = re.fullmatch(r"'?(\w+)'? is undefined", str(root))
		if match:
			field = next((f for f in preview_inputs(doc) if f["field"] == match[1]), None)
			if field:
				return {**result, "code": "MISSING_INPUT", "message": "Für die Vorschau fehlt ein Eingabewert.", "action": "provide_inputs", "issues": [field]}
			result.update(code="UNDEFINED_VARIABLE", message=f"Die Vorlage verwendet die nicht definierte Variable {match[1]}.", issues=[{"field": match[1], "source": "template"}])
	if diagnostic["phase"] == "pdf":
		result.update(action="check_pdf_renderer", message="Die PDF-Erzeugung ist fehlgeschlagen.")
	return result
