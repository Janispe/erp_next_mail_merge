from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cstr, escape_html
from markupsafe import Markup


FOOTER_STYLE = (
	"width: 100%; padding: 1px 0 1px; border-top: 1px solid #000; "
	"font-size: 6pt; color: #000 !important; text-align: center; "
	"font-family: Arial, sans-serif; line-height: 1.05; height: 8mm; "
	"min-height: 8mm; box-sizing: border-box;"
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


def render_footer_blocks(doc: Any | None = None) -> Markup:
	vorlage_name = cstr(getattr(doc, "vorlage", None) or "").strip()
	if not vorlage_name:
		return Markup("")
	try:
		if not frappe.db.exists("Serienbrief Vorlage", vorlage_name):
			return Markup("")
		template = frappe.get_cached_doc("Serienbrief Vorlage", vorlage_name)
	except Exception:
		return Markup("")

	durchlauf = frappe.get_doc(
		{
			"doctype": "Serienbrief Durchlauf",
			"vorlage": vorlage_name,
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
		if not frappe.db.exists("Serienbrief Vorlage", vorlage_name):
			return ""
		vorlage_doc = frappe.get_cached_doc("Serienbrief Vorlage", vorlage_name)
	except Exception:
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
