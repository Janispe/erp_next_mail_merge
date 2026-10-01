import base64
import unittest

from bs4 import BeautifulSoup

from mail_merge.mail_merge.utils.office_export import (
	extract_footer_lines,
	page_margins_mm,
	pick_office_font,
	prepare_html,
)

MARGINS = {"margin_top": 20, "margin_right": 20, "margin_bottom": 16, "margin_left": 25}
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 150"><rect width="10" height="10"/></svg>'

LETTER = """
<div class="serienbrief-root"><div class="serienbrief-page">
<div class="sb-letterhead" style="position: relative; min-height: 4.1cm;">
  <div style="position:absolute; left:0; top:0;">
    <img src="/files/logo.svg" alt="Logo" style="height:1.42cm;width:auto;" />
  </div>
  <div class="sb-address-window">
    <div class="sb-return-address">Absender, Straße 1, 10000 Berlin</div>
    <div class="sb-recipient">Erika Muster<br/>Weg 2<br/>12345 Berlin</div>
  </div>
  <div class="sb-sender"><div>Hausverwaltung<br/>Tel.: 030/1</div>
    <div class="sb-office-hours">Sprechzeiten: Mo</div></div>
</div>
<div class="sb-date">Berlin, den 01.10.2026</div>
<p>Sehr geehrte Frau Muster,</p>
<p style="text-align:justify">Text</p>
<script>alert(1)</script>
<img src="https://example.com/tracker.png" alt="Extern" />
</div></div>
<div id="footer-html"><div style="border-top:1px solid #000"></div><div>Bank: IBAN DE00</div><div>Kategorie / Vorlage</div></div>
"""


def _resolve(src):
	return (SVG, "image/svg+xml") if src == "/files/logo.svg" else None


def _prepare(body=LETTER, footer_lines=("Bank: IBAN DE00", "Kategorie / Vorlage")):
	html = prepare_html(
		body,
		footer_lines=list(footer_lines),
		margins_mm=MARGINS,
		font_family='"HV Liberation Sans", "Liberation Sans", "Arial", sans-serif',
		resolve_image=_resolve,
	)
	return html, BeautifulSoup(html, "html.parser")


class TestOfficeExport(unittest.TestCase):
	def test_font_skips_embedded_only_font_and_maps_liberation_to_arial(self):
		self.assertEqual(pick_office_font('"HV Liberation Sans", "Liberation Sans", Arial'), "Arial")
		self.assertEqual(pick_office_font("'Liberation Serif', serif"), "Times New Roman")
		self.assertEqual(pick_office_font("sans-serif"), "Arial")

	def test_footer_lines_skip_empty_rule(self):
		lines = extract_footer_lines(
			'<div id="footer-html"><div style="border-top:1px"></div><div>A</div><div>B</div></div>'
		)
		self.assertEqual(lines, ["A", "B"])

	def test_letterhead_becomes_table_with_embedded_sized_logo(self):
		_, soup = _prepare()
		self.assertIsNone(soup.select_one(".sb-letterhead"))
		table = soup.find("table")
		left, right = table.find_all("td")
		img = left.find("img")
		self.assertTrue(img["src"].startswith("data:image/svg+xml;base64,"))
		self.assertEqual(base64.b64decode(img["src"].split(",", 1)[1]), SVG)
		# 1,42 cm Höhe → 54 px, Breite aus viewBox-Seitenverhältnis 560:150.
		self.assertEqual((img["height"], img["width"]), ("54", "200"))
		self.assertIn("Erika Muster", left.get_text())
		self.assertIn("Sprechzeiten: Mo", right.get_text())
		self.assertTrue(all(p.get("align") == "right" for p in right.find_all("p")))

	def test_footer_becomes_writer_footer_and_is_removed_from_body(self):
		html, soup = _prepare()
		footer = soup.find("div", attrs={"title": "footer"})
		self.assertEqual([p.get_text() for p in footer.find_all("p")], ["Bank: IBAN DE00", "Kategorie / Vorlage"])
		self.assertIn("border-top", footer.find("p")["style"])
		self.assertNotIn('id="footer-html"', html)

	def test_paragraphs_get_explicit_zero_margins_with_unit(self):
		_, soup = _prepare()
		body_paragraphs = [p for p in soup.find_all("p") if "Frau Muster" in p.get_text() or p.get_text() == "Text"]
		for p in body_paragraphs:
			self.assertIn("margin-top:0cm", p["style"])
			self.assertIn("margin-bottom:0cm", p["style"])
			self.assertIn("line-height:117%", p["style"])
		self.assertIn("text-align:justify", body_paragraphs[1]["style"])

	def test_date_right_aligned(self):
		_, soup = _prepare()
		date = next(p for p in soup.find_all("p") if "01.10.2026" in p.get_text())
		self.assertEqual(date["align"], "right")

	def test_scripts_and_external_images_are_dropped(self):
		html, _ = _prepare()
		self.assertNotIn("<script", html)
		self.assertNotIn("example.com", html)
		self.assertIn("[Extern]", html)

	def test_page_margins_include_chrome_body_margin_and_footer_reserve(self):
		page = page_margins_mm(MARGINS, 2)
		self.assertAlmostEqual(page["margin_left"], 25 + 8 * 25.4 / 96)
		self.assertLess(page["margin_bottom"], 16)
		self.assertEqual(page_margins_mm(MARGINS, 0)["margin_bottom"], 16)
		html, _ = _prepare()
		self.assertIn("@page", html)
		self.assertIn("margin-left: 2.71cm", html)

	def test_pdf_attachment_replaced_by_note(self):
		_, soup = _prepare('<p>Brief</p><div class="hv-pdf-inline-fragment"><embed src="data:application/pdf;base64,AA=="></div>')
		self.assertIsNone(soup.find("embed"))
		self.assertIn("PDF-Anlage", soup.get_text())
