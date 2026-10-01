"""Serienbrief Dokument als bearbeitbares Word- (.docx) oder LibreOffice-Dokument (.odt).

Optionales Feature: aktiv nur, wenn in ``Serienbrief Einstellungen`` der Haken
„Word-/LibreOffice-Export“ gesetzt ist und im Container LibreOffice (``soffice``)
installiert ist. Pfad überschreibbar über den Site-Config-Key ``mail_merge_soffice_path``.

Warum das Druck-HTML nicht einfach durchgereicht wird: Der HTML-Import von
LibreOffice (und genauso der von Word) ist keine Browser-Engine, sondern übersetzt
HTML-Elemente in Absätze, Tabellen und Rahmen und versteht dabei nur etwa CSS1.
Unser Briefbogen lebt aber von Floats, ``position``, ``@font-face``, ``@page`` und
``position: fixed`` für den Footer. Roh konvertiert verrutscht der Briefkopf, die
Schrift fällt auf eine Ersatzschrift zurück und der Footer landet im Fließtext.

Deshalb wird das HTML vorher in Strukturen übersetzt, die Writer/Word nativ kennen:

- Briefkopf (``sb-*``-Klassen aus dem Default-CSS) → rahmenlose 2-Spalten-Tabelle
- ``#footer-html`` → ``<div title="footer">`` (LibreOffice macht daraus die echte Fußzeile)
- Seitenränder aus den Serienbrief-Einstellungen → ``@page`` (wertet LibreOffice aus)
- Schrift → metrisch gleiche System-Schrift (Liberation Sans → Arial)
- Bilder → eingebettet mit festen Pixelmaßen; externe Quellen werden verworfen

Fallen der LibreOffice-Import-Engine, die hier bewusst umgangen werden:

- ``margin: 0`` ohne Einheit wird ignoriert, ``0cm`` greift.
- Absätze ohne Inline-Abstand bekommen 0,5 cm Abstand unten, auch wenn ein
  ``p { margin: 0 }`` im Stylesheet steht → jeder Absatz bekommt Inline-``0cm``.
- ``<img>`` mit URL wird nur verlinkt, nicht eingebettet → data-URI.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from collections.abc import Callable

import frappe
from bs4 import BeautifulSoup, NavigableString, Tag
from frappe import _
from frappe.utils import cint, cstr, escape_html

FORMATS: dict[str, tuple[str, str]] = {
	"docx": (
		"docx:MS Word 2007 XML",
		"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	),
	"odt": ("odt", "application/vnd.oasis.opendocument.text"),
}

CONVERT_TIMEOUT_SECONDS = 90
PX_PER_UNIT = {"px": 1.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "pt": 96 / 72, "in": 96.0}
A4_WIDTH_MM = 210
# Metrisch kompatible Paare: gleiche Laufweite → gleicher Zeilenumbruch wie im PDF.
# Word-Nutzer haben die MS-Schriften, LibreOffice mappt sie zurück auf Liberation.
FONT_SUBSTITUTES = {
	"liberation sans": "Arial",
	"liberation serif": "Times New Roman",
	"liberation mono": "Courier New",
}
GENERIC_FONT_FAMILIES = {"sans-serif", "serif", "monospace", "cursive", "fantasy", "system-ui"}
# Layout aus dem Default-CSS (``_default_css``), das beim Übersetzen verloren geht.
LETTERHEAD_TOP_CM = 0.7
ADDRESS_WINDOW_TOP_CM = 3.2
# CSS-``line-height`` bezieht sich auf die Schriftgröße, LibreOffice-Prozent aber auf die
# natürliche Zeilenhöhe der Schrift (Arial/Liberation Sans: 1,149 em) → umrechnen.
FONT_NATURAL_LINE_HEIGHT = 1.149
BODY_LINE_HEIGHT = 1.35
SENDER_LINE_HEIGHT = 1.25
FOOTER_LINE_HEIGHT = 1.05
FOOTER_FONT_PT = 6
# Das PDF setzt den Chrome-Default-Rand von <body> (8px) nicht zurück; der Brief sitzt
# dort also 8px weiter innen als die konfigurierten Seitenränder.
CHROME_BODY_MARGIN_MM = 8 * 25.4 / 96
# Im PDF liegt der Footer im unteren Seitenrand. In Writer/Word nimmt die Fußzeile dem
# Textbereich Platz weg → ihre Höhe vom unteren Rand abziehen, sonst bricht Word früher um.
FOOTER_GAP_MM = 2.0
MIN_BOTTOM_MARGIN_MM = 4.0
DROP_TAGS = ("script", "style", "link", "meta", "embed", "iframe", "object", "noscript")


# ---------------------------------------------------------------------------
# Verfügbarkeit
# ---------------------------------------------------------------------------


def soffice_binary() -> str | None:
	configured = cstr(frappe.conf.get("mail_merge_soffice_path") or "").strip()
	if configured:
		return configured if shutil.which(configured) else None
	return shutil.which("soffice") or shutil.which("libreoffice")


def is_enabled() -> bool:
	try:
		return bool(cint(frappe.db.get_single_value("Serienbrief Einstellungen", "office_export_aktiv")))
	except Exception:
		return False


@frappe.whitelist()
def get_office_export_status() -> dict[str, bool]:
	enabled = is_enabled()
	return {"enabled": enabled, "available": bool(enabled and soffice_binary())}


# ---------------------------------------------------------------------------
# HTML → Word-taugliches HTML (rein, ohne Frappe-Zugriffe → testbar)
# ---------------------------------------------------------------------------


def pick_office_font(css_font_family: str) -> str:
	"""Erste echte Schrift aus einer CSS-Font-Liste, ohne nur per @font-face eingebettete
	(``HV …``) und mit metrisch gleichem MS-Ersatz für Liberation."""
	for raw in cstr(css_font_family).split(","):
		name = raw.strip().strip("\"'").strip()
		if not name or name.lower() in GENERIC_FONT_FAMILIES or name.startswith("HV "):
			continue
		return FONT_SUBSTITUTES.get(name.lower(), name)
	return "Arial"


def _length_px(value: str | None) -> float | None:
	match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(px|cm|mm|pt|in)?\s*", cstr(value))
	if not match:
		return None
	return float(match.group(1)) * PX_PER_UNIT[match.group(2) or "px"]


def _style_value(style: str, prop: str) -> str | None:
	match = re.search(rf"(?:^|;)\s*{prop}\s*:\s*([^;]+)", cstr(style), re.I)
	return match.group(1).strip() if match else None


def _intrinsic_size(data: bytes, mime: str) -> tuple[float, float] | None:
	if "svg" in mime:
		head = data[:4000].decode("utf-8", "ignore")
		svg = re.search(r"<svg\b[^>]*>", head, re.S)
		if not svg:
			return None
		tag = svg.group(0)
		width = _length_px(_attr(tag, "width"))
		height = _length_px(_attr(tag, "height"))
		if width and height:
			return width, height
		viewbox = _attr(tag, "viewBox")
		parts = cstr(viewbox).replace(",", " ").split()
		if len(parts) == 4:
			try:
				return float(parts[2]), float(parts[3])
			except ValueError:
				return None
		return None
	try:
		from PIL import Image

		with Image.open(BytesIO(data)) as image:
			return float(image.width), float(image.height)
	except Exception:
		return None


def _attr(tag_source: str, name: str) -> str | None:
	match = re.search(rf'\s{name}\s*=\s*"([^"]*)"', tag_source)
	return match.group(1) if match else None


def _embed_image(img: Tag, resolve_image: Callable[[str], tuple[bytes, str] | None], max_width_px: float):
	src = cstr(img.get("src")).strip()
	resolved = None
	if src.startswith("data:"):
		match = re.match(r"data:([^;,]+)(;base64)?,(.*)", src, re.S)
		if match and match.group(2):
			try:
				resolved = (base64.b64decode(match.group(3)), match.group(1))
			except Exception:
				resolved = None
	elif src:
		resolved = resolve_image(src)
	if not resolved:
		# Nicht auflösbar oder extern: nicht an LibreOffice weiterreichen (würde sonst
		# serverseitig eine beliebige URL abrufen) — stattdessen Alt-Text stehen lassen.
		alt = cstr(img.get("alt")).strip()
		if alt:
			img.replace_with(NavigableString(f"[{alt}]"))
		else:
			img.decompose()
		return

	data, mime = resolved
	style = cstr(img.get("style"))
	width = _length_px(_style_value(style, "width")) or _length_px(img.get("width"))
	height = _length_px(_style_value(style, "height")) or _length_px(img.get("height"))
	intrinsic = _intrinsic_size(data, mime)
	if intrinsic:
		ratio = intrinsic[0] / intrinsic[1] if intrinsic[1] else 1
		if width and not height:
			height = width / ratio
		elif height and not width:
			width = height * ratio
		elif not width and not height:
			width, height = intrinsic
	if width and height and width > max_width_px:
		height = height * max_width_px / width
		width = max_width_px

	img["src"] = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
	del img["style"]
	if width and height:
		img["width"] = str(round(width))
		img["height"] = str(round(height))


def _set_inline(tag: Tag, **props: str):
	style = cstr(tag.get("style")).strip().rstrip(";")
	for prop, value in props.items():
		css_prop = prop.replace("_", "-")
		style = re.sub(rf"(?:^|;)\s*{css_prop}\s*:[^;]*", "", style, flags=re.I).strip(";").strip()
		style = f"{style};{css_prop}:{value}" if style else f"{css_prop}:{value}"
	tag["style"] = style


def _line_height_pct(css_line_height: float) -> str:
	return f"{round(css_line_height / FONT_NATURAL_LINE_HEIGHT * 100)}%"


def _lines_html(node: Tag | None) -> str:
	"""Textzeilen eines Blocks (Divs/<br>) als ``<br>``-getrennter, escapeter Text."""
	if node is None:
		return ""
	return "<br>".join(escape_html(line) for line in node.stripped_strings)


def _letterhead_table(letterhead: Tag) -> BeautifulSoup:
	window = letterhead.select_one(".sb-address-window")
	sender = letterhead.select_one(".sb-sender")
	logos = [
		img
		for img in letterhead.find_all("img")
		if not img.find_parent(class_=["sb-address-window", "sb-sender"])
	]
	return_address = window.select_one(".sb-return-address") if window else None
	recipient = window.select_one(".sb-recipient") if window else None
	office_hours = sender.select_one(".sb-office-hours") if sender else None
	if office_hours is not None:
		office_hours.extract()

	left: list[str] = []
	logo_height_cm = 0.0
	for img in logos:
		img.extract()
		logo_height_cm = max(logo_height_cm, (_length_px(img.get("height")) or 0) / PX_PER_UNIT["cm"])
		left.append(f'<p style="margin-top:0cm;margin-bottom:0cm">{img}</p>')
	# Adressfeld sitzt im PDF 3,2 cm unter der Briefkopf-Oberkante (Fensterkuvert).
	gap_cm = max(ADDRESS_WINDOW_TOP_CM - logo_height_cm, 0.3)
	if return_address is not None:
		left.append(
			f'<p style="margin-top:{gap_cm:.2f}cm;margin-bottom:0.15cm;font-size:7pt">'
			f"<u>{escape_html(return_address.get_text(' ', strip=True))}</u></p>"
		)
		gap_cm = 0
	if recipient is not None:
		left.append(
			f'<p style="margin-top:{gap_cm:.2f}cm;margin-bottom:0cm;font-size:10pt">{_lines_html(recipient)}</p>'
		)

	right: list[str] = []
	if sender is not None:
		right.append(
			'<p align="right" style="margin-top:0cm;margin-bottom:0cm;font-size:9pt;line-height:'
			f'{_line_height_pct(SENDER_LINE_HEIGHT)}">'
			f"{_lines_html(sender)}</p>"
		)
	if office_hours is not None:
		right.append(
			'<p align="right" style="margin-top:0.15cm;margin-bottom:0cm;font-size:7.5pt">'
			f"{_lines_html(office_hours)}</p>"
		)

	table = (
		f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
		f'style="margin-top:{LETTERHEAD_TOP_CM}cm">'
		'<tr><td width="60%" valign="top">' + "".join(left) + "</td>"
		'<td width="40%" valign="top">' + "".join(right) + "</td></tr></table>"
	)
	return BeautifulSoup(table, "html.parser")


def extract_footer_lines(footer_html: str) -> list[str]:
	soup = BeautifulSoup(cstr(footer_html), "html.parser")
	root = soup.find(id="footer-html") or soup
	lines: list[str] = []
	for child in root.find_all(recursive=False):
		text = child.get_text(" ", strip=True)
		if text:
			lines.append(text)
	return lines


def page_margins_mm(margins_mm: dict[str, float], footer_line_count: int) -> dict[str, float]:
	"""Seitenränder so, dass der Textbereich derselbe ist wie im PDF."""
	footer_mm = 0.0
	if footer_line_count:
		line_mm = FOOTER_FONT_PT * FOOTER_LINE_HEIGHT * 25.4 / 72
		footer_mm = FOOTER_GAP_MM + 0.5 + footer_line_count * line_mm
	return {
		"margin_top": margins_mm["margin_top"] + CHROME_BODY_MARGIN_MM,
		"margin_right": margins_mm["margin_right"] + CHROME_BODY_MARGIN_MM,
		"margin_bottom": max(margins_mm["margin_bottom"] - footer_mm, MIN_BOTTOM_MARGIN_MM),
		"margin_left": margins_mm["margin_left"] + CHROME_BODY_MARGIN_MM,
	}


def prepare_html(
	body_html: str,
	*,
	footer_lines: list[str],
	margins_mm: dict[str, float],
	font_family: str,
	resolve_image: Callable[[str], tuple[bytes, str] | None],
	title: str = "",
) -> str:
	"""Übersetzt gerendertes Serienbrief-HTML in HTML, das LibreOffice sauber importiert."""
	soup = BeautifulSoup(cstr(body_html), "html.parser")

	for tag in soup.find_all(DROP_TAGS):
		tag.decompose()
	for footer in soup.select("#footer-html"):
		footer.decompose()
	# Eingebettete PDF-Anlagen (Chrome-Hybrid-Pfad) lassen sich nicht in Word übernehmen.
	for fragment in soup.select(".hv-pdf-inline-fragment"):
		note = soup.new_tag("p")
		note.string = _("[PDF-Anlage – im Word-/LibreOffice-Export nicht enthalten]")
		fragment.replace_with(note)

	page = page_margins_mm(margins_mm, len(footer_lines))
	content_width_px = (A4_WIDTH_MM - page["margin_left"] - page["margin_right"]) * PX_PER_UNIT["mm"]
	for img in soup.find_all("img"):
		_embed_image(img, resolve_image, content_width_px)

	for letterhead in soup.select(".sb-letterhead"):
		letterhead.replace_with(_letterhead_table(letterhead))

	for date in soup.select(".sb-date"):
		date.name = "p"
		date.attrs = {"align": "right", "style": "margin-top:0.5cm;margin-bottom:0cm"}
		date.string = date.get_text(" ", strip=True)

	# Inline statt Stylesheet: Absätze in Tabellenzellen bekommen in LibreOffice die
	# Vorlage „Tabelleninhalt“, auf die eine ``p``-Regel nicht wirkt.
	for p in soup.find_all(["p", "li"]):
		style = cstr(p.get("style"))
		if p.name == "p" and not _style_value(style, "margin-top"):
			_set_inline(p, margin_top="0cm")
		if p.name == "p" and not _style_value(style, "margin-bottom"):
			_set_inline(p, margin_bottom="0cm")
		if not _style_value(style, "line-height"):
			_set_inline(p, line_height=_line_height_pct(BODY_LINE_HEIGHT))

	office_font = pick_office_font(font_family)
	footer_paragraphs = "".join(
		f'<p style="margin-top:{FOOTER_GAP_MM / 10 if index == 0 else 0:.2f}cm;'
		f"margin-bottom:0cm;font-size:{FOOTER_FONT_PT}pt;font-family:Arial;"
		f'line-height:{_line_height_pct(FOOTER_LINE_HEIGHT)}'
		f'{";border-top:1px solid #000000;padding-top:1px" if index == 0 else ""}">'
		f"{escape_html(line)}</p>"
		for index, line in enumerate(footer_lines)
	)
	page = page_margins_mm(margins_mm, len(footer_lines))
	css = f"""
@page {{ size: 21cm 29.7cm; margin-top: {page['margin_top'] / 10:.2f}cm;
	margin-right: {page['margin_right'] / 10:.2f}cm; margin-bottom: {page['margin_bottom'] / 10:.2f}cm;
	margin-left: {page['margin_left'] / 10:.2f}cm }}
body, p, td, li {{ font-family: "{office_font}"; font-size: 11pt; color: #222222 }}
"""
	return (
		'<!DOCTYPE html><html><head><meta charset="utf-8">'
		f"<title>{escape_html(title)}</title><style>{css}</style></head><body>"
		+ (f'<div title="footer">{footer_paragraphs}</div>' if footer_paragraphs else "")
		+ str(soup)
		+ "</body></html>"
	)


# ---------------------------------------------------------------------------
# LibreOffice-Aufruf
# ---------------------------------------------------------------------------


def convert_html(html: str, fmt: str) -> bytes:
	if fmt not in FORMATS:
		frappe.throw(_("Unbekanntes Format: {0}").format(fmt))
	binary = soffice_binary()
	if not binary:
		frappe.throw(
			_(
				"LibreOffice (soffice) ist auf dem Server nicht installiert. "
				"Der Word-/LibreOffice-Export braucht es im Backend-Image."
			)
		)
	with tempfile.TemporaryDirectory(prefix="mm-office-") as tmp:
		source = Path(tmp) / "brief.html"
		source.write_text(html, encoding="utf-8")
		# Eigenes Profil pro Aufruf: LibreOffice sperrt sein Profil, parallele
		# Exporte mit gemeinsamem Profil würden sich gegenseitig blockieren.
		profile = Path(tmp) / "profile"
		command = [
			binary,
			f"-env:UserInstallation={profile.as_uri()}",
			"--headless",
			"--norestore",
			"--infilter=HTML (StarWriter)",
			"--convert-to",
			FORMATS[fmt][0],
			"--outdir",
			tmp,
			str(source),
		]
		try:
			result = subprocess.run(
				command,
				check=False,
				capture_output=True,
				timeout=CONVERT_TIMEOUT_SECONDS,
				env={**os.environ, "HOME": tmp},
			)
		except subprocess.TimeoutExpired:
			frappe.throw(_("LibreOffice hat für die Umwandlung zu lange gebraucht."))
		target = Path(tmp) / f"brief.{fmt}"
		if result.returncode != 0 or not target.exists():
			frappe.log_error(
				title="Serienbrief Office-Export fehlgeschlagen",
				message=f"{command}\n\nstdout:\n{result.stdout!r}\n\nstderr:\n{result.stderr!r}",
			)
			frappe.throw(_("Die Umwandlung mit LibreOffice ist fehlgeschlagen. Details im Error Log."))
		return target.read_bytes()


# ---------------------------------------------------------------------------
# Serienbrief Dokument → Datei
# ---------------------------------------------------------------------------


def _resolve_site_image(src: str) -> tuple[bytes, str] | None:
	path: str | None = None
	url = src.split("?", 1)[0]
	if url.startswith("/private/files/"):
		path = frappe.get_site_path("private", "files", url[len("/private/files/"):])
	elif url.startswith("/files/"):
		path = frappe.get_site_path("public", "files", url[len("/files/"):])
	elif url.startswith("/assets/"):
		path = os.path.join(frappe.local.sites_path, url.lstrip("/"))
	if not path:
		return None
	resolved = Path(path).resolve()
	# Kein Ausbruch aus dem Dateiverzeichnis über ``..``.
	allowed_roots = (
		Path(frappe.get_site_path("private", "files")).resolve(),
		Path(frappe.get_site_path("public", "files")).resolve(),
		Path(frappe.local.sites_path, "assets").resolve(),
	)
	if not any(resolved.is_relative_to(root) for root in allowed_roots) or not resolved.is_file():
		return None
	mime = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
	if not mime.startswith("image/"):
		return None
	return resolved.read_bytes(), mime


def _safe_filename(value: str) -> str:
	# Nur Zeichen ersetzen, die Windows/macOS in Dateinamen verbieten; Titel bleiben lesbar.
	name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", cstr(value))
	name = re.sub(r"\s+", " ", name).strip(" .")
	return (name or "serienbrief")[:120]


def render_dokument(dokument: str, fmt: str) -> tuple[str, bytes]:
	from mail_merge.install import get_serienbrief_margins
	from mail_merge.mail_merge.utils.brand_print import apply_print_saving_brand_assets
	from mail_merge.mail_merge.utils.footer import render_document_footer_html
	from mail_merge.mail_merge.utils.serienbrief_fonts import serienbrief_font_family

	doc = frappe.get_doc("Serienbrief Dokument", dokument)
	doc.check_permission("read")
	if cstr(doc.get("status")) in ("Fehler", "Übersprungen"):
		frappe.throw(_("Für dieses Dokument wurde kein Brief erzeugt ({0}).").format(doc.status))
	body = cstr(doc.get("html")).strip()
	if not body:
		frappe.throw(_("Das Dokument enthält noch keinen gerenderten Brief."))

	# Gleiche HTML-Transformation wie der PDF-Pfad (z. B. ausgeblendete Logos).
	body = apply_print_saving_brand_assets(body, False)
	html = prepare_html(
		body,
		footer_lines=extract_footer_lines(str(render_document_footer_html(doc))),
		margins_mm=get_serienbrief_margins(),
		font_family=serienbrief_font_family(),
		resolve_image=_resolve_site_image,
		title=cstr(doc.get("title") or doc.name),
	)
	filename = f"{_safe_filename(doc.get('title') or doc.name)}-{doc.name}.{fmt}"
	return filename, convert_html(html, fmt)


@frappe.whitelist()
def download_dokument(dokument: str, format: str = "docx"):
	fmt = cstr(format).strip().lower()
	if fmt not in FORMATS:
		frappe.throw(_("Unbekanntes Format: {0}").format(format))
	if not is_enabled():
		frappe.throw(_("Der Word-/LibreOffice-Export ist in den Serienbrief Einstellungen nicht aktiviert."))
	filename, content = render_dokument(dokument, fmt)
	frappe.local.response.filename = filename
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"
