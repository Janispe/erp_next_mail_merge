from __future__ import annotations

import frappe

from mail_merge.mail_merge.utils.serienbrief_fonts import (
	get_serienbrief_font_face_css,
	serienbrief_font_family,
)


SERIENBRIEF_MARGIN_DEFAULTS: dict[str, float] = {
	"margin_top": 20.0,
	"margin_right": 20.0,
	"margin_bottom": 16.0,
	"margin_left": 25.0,
}

SERIENBRIEF_SETTINGS_DEFAULTS: dict[str, object] = {
	"picker_modal_width_vw": 92,
	"serienbrief_pdf_skip_dialog": 1,
	"serienbrief_pdf_default_format": "Serienbrief Dokument",
}


def ensure_serienbrief_settings_defaults() -> None:
	"""Persist generic settings defaults for existing sites after schema updates."""

	if not frappe.db.exists("DocType", "Serienbrief Einstellungen"):
		return
	for fieldname, value in SERIENBRIEF_SETTINGS_DEFAULTS.items():
		try:
			current = frappe.db.get_single_value("Serienbrief Einstellungen", fieldname)
		except Exception:
			continue
		if current in (None, ""):
			frappe.db.set_single_value("Serienbrief Einstellungen", fieldname, value)


def get_serienbrief_margins() -> dict[str, float]:
	"""Read configured PDF page margins for Serienbrief documents."""

	margins = dict(SERIENBRIEF_MARGIN_DEFAULTS)
	try:
		if frappe.db.exists("DocType", "Serienbrief Einstellungen"):
			for key in margins:
				val = frappe.db.get_single_value("Serienbrief Einstellungen", key)
				if val is None:
					continue
				try:
					f = float(val)
				except (TypeError, ValueError):
					continue
				if f > 0:
					margins[key] = f
	except Exception:
		pass
	return margins


def ensure_serienbrief_dokument_print_format() -> None:
	_ensure_serienbrief_dokument_print_format(reason="hook")


def _ensure_serienbrief_dokument_print_format(*, reason: str) -> None:
	"""Create/update the generic Print Format used for Serienbrief Dokument PDFs."""

	try:
		if not frappe.db.exists("DocType", "Serienbrief Dokument"):
			return

		name = "Serienbrief Dokument"
		m = get_serienbrief_margins()
		page_block = (
			"\n\t\t\t@page {\n"
			"\t\t\t\tsize: A4;\n"
			f"\t\t\t\tmargin: {m['margin_top']}mm {m['margin_right']}mm "
			f"{m['margin_bottom']}mm {m['margin_left']}mm;\n"
			"\t\t\t}\n"
			"\t\t\tbody {\n"
			"\t\t\t\tmargin: 0;\n"
			"\t\t\t}\n"
		)
		css = (page_block + get_serienbrief_font_face_css() + """
			body,
			.serienbrief-root,
			.print-format,
			.print-format .serienbrief-root {
				font-family: __MAIL_MERGE_FONT_FAMILY__;
				font-size: 11pt;
				line-height: 1.35;
			}
			.mail-merge-draft-watermark-layer {
				position: fixed;
				top: 0;
				left: 0;
				right: 0;
				bottom: 0;
				z-index: 9999;
				pointer-events: none;
				user-select: none;
			}
			.mail-merge-draft-watermark {
				position: absolute;
				top: 50%;
				left: 50%;
				width: 140%;
				text-align: center;
				line-height: 1;
				-webkit-transform: translate(-50%, -50%) rotate(-45deg);
				transform: translate(-50%, -50%) rotate(-45deg);
				-webkit-transform-origin: 50% 50%;
				transform-origin: 50% 50%;
				font-size: 110pt;
				font-weight: 700;
				letter-spacing: 0.18em;
				color: rgba(200, 0, 0, 0.14);
				text-transform: uppercase;
				white-space: nowrap;
			}
			.sb-letterhead {
				margin-top: 0.7cm;
			}
			.sb-address-window {
				float: left;
				width: 60%;
				padding-top: 3.2cm;
				font-size: 10pt;
				box-sizing: border-box;
			}
			.sb-return-address {
				font-size: 7pt;
				text-decoration: underline;
				margin-bottom: 0.15cm;
			}
			.sb-sender {
				float: right;
				width: 40%;
				text-align: right;
				font-size: 9pt;
				box-sizing: border-box;
			}
			.sb-office-hours {
				font-size: 7.5pt;
				margin-top: 0.15cm;
			}
			.sb-letterhead:after {
				content: "";
				display: block;
				clear: both;
			}
			.sb-date {
				margin-top: 0.5cm;
				text-align: right;
			}
			.print-format {
				margin: 0 !important;
				padding: 0 !important;
				width: 100% !important;
				max-width: 100% !important;
				box-sizing: border-box;
			}
			.serienbrief-page {
				page-break-after: always;
				padding: 0;
			}
			.serienbrief-page:last-child {
				page-break-after: auto;
			}
			.serienbrief-page p {
				margin: 0;
				line-height: 1.35;
			}
			.serienbrief-page p:empty::before {
				content: "\\00a0";
			}
			.serienbrief-page table {
				border-collapse: collapse;
			}
			.print-format .serienbrief-page td,
			.print-format .serienbrief-page th {
				padding: 2px 6px !important;
				vertical-align: top;
			}
			.print-format .serienbrief-page table[data-hv-borders] td,
			.print-format .serienbrief-page table[data-hv-borders] th {
				border: 1px solid #000 !important;
			}
			.serienbrief-block {
				margin-bottom: 12px;
			}
			.serienbrief-block:last-child {
				margin-bottom: 0;
			}
			[style*="color"] strong,
			[style*="color"] b,
			[style*="color"] em,
			[style*="color"] i,
			[style*="color"] u,
			[style*="color"] span,
			[style*="color"] a,
			[style*="color"] sup,
			[style*="color"] sub {
				color: inherit !important;
			}
			@media print {
				.print-hide,
				.action-banner {
					display: none !important;
				}
			}
		""").replace("__MAIL_MERGE_FONT_FAMILY__", serienbrief_font_family())

		footer_html = """
<div id="footer-html" style="width: 100%; padding: 1px 0 1px; border-top: 1px solid #000; font-size: 6pt; color: #000 !important; text-align: center; font-family: Arial, sans-serif; line-height: 1.05; height: 8mm; min-height: 8mm; box-sizing: border-box;">
{%- set vorlage_name = doc.vorlage if doc and doc.vorlage else None -%}
{%- set pfad_html = "" -%}
{%- if vorlage_name and frappe.db.exists("Serienbrief Vorlage", vorlage_name) -%}
{%- set vorlage_doc = frappe.get_cached_doc("Serienbrief Vorlage", vorlage_name) -%}
{%- set ns = namespace(current=vorlage_doc.kategorie, chain=[]) -%}
{%- for _ in range(20) -%}
{%- if ns.current and frappe.db.exists("Serienbrief Kategorie", ns.current) -%}
{%- set kat_doc = frappe.get_cached_doc("Serienbrief Kategorie", ns.current) -%}
{%- set ns.chain = ns.chain + [kat_doc.title or ns.current] -%}
{%- set ns.current = kat_doc.parent_serienbrief_kategorie -%}
{%- else -%}
{%- set ns.current = None -%}
{%- endif -%}
{%- endfor -%}
{%- set pfad_parts = (ns.chain | reverse | list) + [vorlage_doc.title or vorlage_name] -%}
{%- set pfad_html = pfad_parts | join(" / ") -%}
{%- endif -%}
{%- if pfad_html -%}<div style="font-size: 6pt !important; line-height: 1.05 !important; color: #000 !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ pfad_html }}</div>{%- endif -%}
</div>
"""

		html = f"""<style>{css}</style>
{{% if doc.docstatus == 0 %}}
<div class="mail-merge-draft-watermark-layer"><div class="mail-merge-draft-watermark">DRAFT</div></div>
{{% endif %}}
{{{{ (doc.html or '') | safe }}}}
{footer_html}"""

		if frappe.db.exists("Print Format", name):
			doc = frappe.get_doc("Print Format", name)
			changed = False
			if doc.doc_type != "Serienbrief Dokument":
				doc.doc_type = "Serienbrief Dokument"
				changed = True
			if doc.print_format_type != "Jinja":
				doc.print_format_type = "Jinja"
				changed = True
			if int(getattr(doc, "custom_format", 0) or 0) != 1:
				doc.custom_format = 1
				changed = True
			if (doc.html or "").strip() != html.strip():
				doc.html = html
				changed = True
			if int(getattr(doc, "disabled", 0) or 0) != 0:
				doc.disabled = 0
				changed = True
			if changed:
				doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": name,
					"doc_type": "Serienbrief Dokument",
					"print_format_type": "Jinja",
					"custom_format": 1,
					"html": html,
				}
			).insert(ignore_permissions=True)

		try:
			frappe.db.commit()
		except Exception:
			pass
	except Exception:
		try:
			frappe.log_error(
				frappe.get_traceback(),
				f"mail_merge Serienbrief Dokument Print Format setup failed ({reason})",
			)
		except Exception:
			pass


def ensure_serienbrief_print_format_link_field() -> None:
	_ensure_serienbrief_print_format_link_field(reason="hook")


def _ensure_serienbrief_print_format_link_field(*, reason: str) -> None:
	try:
		from mail_merge.mail_merge.patches.post_model_sync.add_serienbrief_vorlage_to_print_format import (
			execute,
		)

		execute()
		try:
			frappe.db.commit()
		except Exception:
			pass
	except Exception:
		try:
			frappe.log_error(
				frappe.get_traceback(),
				f"mail_merge Print Format Serienbrief field setup failed ({reason})",
			)
		except Exception:
			pass
