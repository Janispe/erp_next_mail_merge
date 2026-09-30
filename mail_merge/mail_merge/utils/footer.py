from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cstr, escape_html
from markupsafe import Markup


FOOTER_STYLE = (
	"width: 100%; padding: 0 0 1px; "
	"font-size: 6pt; color: #000 !important; text-align: center; "
	"font-family: Arial, sans-serif; line-height: 1.05; height: 8mm; "
	"min-height: 8mm; box-sizing: border-box;"
)

FOOTER_RULE_STYLE = (
	"width: 100%; border-top: 1px solid #000; height: 0; "
	"line-height: 0; font-size: 0; margin: 0 0 1px; padding: 0;"
)

FOOTER_ROW_STYLE = (
	"font-size: 6pt !important; line-height: 1.05 !important; "
	"color: #000 !important; white-space: nowrap; overflow: hidden; "
	"text-overflow: ellipsis;"
)


def render_footer_extensions(doc: Any | None = None) -> Markup:
	"""Render app-provided footer rows for Serienbrief PDFs.

	The core only defines the extension point. Domain apps decide which rows
	they contribute through the ``mail_merge_pdf_footer_renderers`` hook.
	"""

	parts: list[str] = []
	for dotted_path in frappe.get_hooks("mail_merge_pdf_footer_renderers") or []:
		renderer = frappe.get_attr(dotted_path)
		html = cstr(renderer(doc))
		if html.strip():
			parts.append(html)
	return Markup("\n".join(parts))


def _fixed_template_version(doc: Any | None) -> str:
	"""Vom Durchlauf gewählte Vorlagenversion; leer = aktueller Stand.

	``Serienbrief Dokument.vorlagenversion`` ist nur ein Nachweis (immer gesetzt) und
	entscheidet deshalb nicht; massgeblich ist das Feld des Durchlaufs.
	"""
	if cstr(getattr(doc, "doctype", None) or "") == "Serienbrief Dokument":
		durchlauf = cstr(getattr(doc, "durchlauf", None) or "").strip()
		if not durchlauf or not frappe.get_meta("Serienbrief Durchlauf").has_field("vorlagenversion"):
			return ""
		return cstr(frappe.db.get_value("Serienbrief Durchlauf", durchlauf, "vorlagenversion") or "")
	return cstr(getattr(doc, "vorlagenversion", None) or "")


def _footer_template(doc: Any | None, vorlage_name: str):
	from mail_merge.mail_merge.utils.textbaustein_versions import template_at_version

	version = _fixed_template_version(doc)
	if not version and not frappe.db.exists("Serienbrief Vorlage", vorlage_name):
		return None
	return template_at_version(vorlage_name, version or None)


def render_footer_blocks(doc: Any | None = None) -> Markup:
	vorlage_name = cstr(getattr(doc, "vorlage", None) or "").strip()
	if not vorlage_name:
		return Markup("")
	try:
		template = _footer_template(doc, vorlage_name)
	except Exception:
		return Markup("")
	if not template:
		return Markup("")

	durchlauf = frappe.get_doc(
		{
			"doctype": "Serienbrief Durchlauf",
			"vorlage": vorlage_name,
			"vorlagenversion": _fixed_template_version(doc) or None,
			"iteration_doctype": cstr(getattr(doc, "iteration_doctype", None) or getattr(template, "haupt_verteil_objekt", None) or ""),
			"date": getattr(doc, "date", None) or frappe.utils.today(),
		}
	)
	return Markup(durchlauf.render_footer_blocks(template, footer_doc=doc))


def render_template_path_footer(doc: Any | None = None) -> str:
	vorlage_name = cstr(getattr(doc, "vorlage", None) or "").strip()
	if not vorlage_name:
		return ""
	try:
		vorlage_doc = _footer_template(doc, vorlage_name)
	except Exception:
		return ""
	if not vorlage_doc:
		return ""

	chain: list[str] = []
	current = cstr(getattr(vorlage_doc, "kategorie", "") or "").strip()
	for _ in range(20):
		if not current:
			break
		try:
			if not frappe.db.exists("Serienbrief Kategorie", current):
				break
			kat_doc = frappe.get_cached_doc("Serienbrief Kategorie", current)
		except Exception:
			break
		chain.append(cstr(getattr(kat_doc, "title", None) or current))
		current = cstr(getattr(kat_doc, "parent_serienbrief_kategorie", "") or "").strip()

	parts = list(reversed(chain)) + [cstr(getattr(vorlage_doc, "title", None) or vorlage_name)]
	return " / ".join(part for part in parts if part)


def render_document_footer_html(doc: Any | None = None) -> Markup:
	rows: list[str] = []
	rows.append(f'<div style="{FOOTER_RULE_STYLE}"></div>')
	block_html = cstr(render_footer_blocks(doc)).strip()
	if block_html:
		rows.append(f'<div style="{FOOTER_ROW_STYLE}">{block_html}</div>')

	extension_html = cstr(render_footer_extensions(doc)).strip()
	if extension_html:
		rows.append(extension_html)

	path_html = render_template_path_footer(doc)
	if path_html:
		rows.append(f'<div style="{FOOTER_ROW_STYLE}">{escape_html(path_html)}</div>')

	return Markup(f'<div id="footer-html" style="{FOOTER_STYLE}">\n' + "\n".join(rows) + "\n</div>")
