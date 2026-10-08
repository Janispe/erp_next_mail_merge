"""Bounded local files and PDF configuration for assistant-authored blocks."""

import re
from io import BytesIO
from pathlib import Path

import frappe
from pypdf import PdfReader

from mail_merge.mail_merge.utils.serienbrief_pdf_form import parse_pdf_pages

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100
PATH_RE = re.compile(r"[A-Za-z]\w*(\[\])?(\.[A-Za-z]\w*(\[\])?)*")


def local_file_content(file_doc):
	file_doc.check_permission("read")
	url = file_doc.file_url or ""
	for prefix, directory in (("/private/files/", "private"), ("/files/", "public")):
		if url.startswith(prefix):
			root = Path(frappe.get_site_path(directory, "files")).resolve()
			path = (root / url[len(prefix) :]).resolve()
			if not path.is_relative_to(root) or not path.is_file():
				break
			if path.stat().st_size > MAX_FILE_BYTES:
				frappe.throw("Datei zu groß (maximal 10 MiB).")
			return path.read_bytes()
	frappe.throw("Nur lokale Frappe-Dateien sind erlaubt; keine URLs oder Dateipfade.")


def pdf_info(content):
	if not isinstance(content, bytes) or not content.startswith(b"%PDF-") or len(content) > MAX_FILE_BYTES:
		frappe.throw("Ungültige PDF-Datei oder mehr als 10 MiB.")
	try:
		reader = PdfReader(BytesIO(content))
		if reader.is_encrypted:
			frappe.throw("Verschlüsselte PDFs werden nicht unterstützt.")
		pages = len(reader.pages)
		if not 1 <= pages <= MAX_PDF_PAGES:
			frappe.throw("PDF muss 1 bis 100 Seiten enthalten.")
		form = reader.trailer["/Root"].get("/AcroForm")
		if form and form.get_object().get("/XFA"):
			frappe.throw("XFA-Formulare werden nicht unterstützt.")
		fields = sorted((reader.get_fields() or {}).keys())
		if len(fields) > 100:
			frappe.throw("PDF darf höchstens 100 Formularfelder enthalten.")
		return {"page_count": pages, "field_names": fields}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.throw("PDF-Datei konnte nicht gelesen werden.")


def pdf_file_info(url):
	files = (
		frappe.get_list("File", filters={"file_url": url, "is_folder": 0}, pluck="name", limit_page_length=1)
		if url
		else []
	)
	if not files:
		frappe.throw("Eine lesbare lokale PDF-Datei ist erforderlich.")
	return pdf_info(local_file_content(frappe.get_doc("File", files[0])))


def validate_pdf_block(doc):
	"""Check files and mappings on creation, proposals and editor adoption."""
	info = pdf_file_info(doc.get("pdf_file"))
	pages = doc.get("pdf_pages") or ""
	if not isinstance(pages, str) or len(pages) > 400:
		frappe.throw("Ungültige PDF-Seitenauswahl.")
	parse_pdf_pages(pages, info["page_count"])
	if doc.get("pdf_flatten") not in (0, 1, True, False):
		frappe.throw("pdf_flatten muss ein Boolean sein.")
	# Parent paths belong in standardpfade; mappings read isolated block inputs.
	roots = {frappe.scrub(row.variable) for row in doc.get("variables") or []}
	seen = set()
	mappings = doc.get("pdf_field_mappings") or []
	if len(mappings) > 100:
		frappe.throw("Höchstens 100 PDF-Feldzuordnungen sind erlaubt.")
	for row in mappings:
		name, path = row.get("pdf_field_name"), row.get("value_path") or ""
		if name not in info["field_names"] or name in seen:
			frappe.throw("PDF-Feld fehlt oder ist mehrfach zugeordnet.")
		seen.add(name)
		if (
			not isinstance(path, str)
			or len(path) > 240
			or (path and (not PATH_RE.fullmatch(path) or path.split(".", 1)[0] not in roots))
		):
			frappe.throw(
				"PDF-Wertpfad muss bei einer deklarierten Bausteinvariable beginnen; Empfängerpfade gehören in standardpfade."
			)
		if row.get("value_type") not in ("String", "Zahl", "Bool", "Datum") or row.get("required") not in (
			0,
			1,
			True,
			False,
		):
			frappe.throw("Ungültiger Typ oder Pflichtschalter im PDF-Mapping.")
		fallback = row.get("fallback_value")
		if fallback is not None and (not isinstance(fallback, str) or len(fallback) > 4000):
			frappe.throw("PDF-Fallback muss Text mit höchstens 4000 Zeichen sein.")
	return info
