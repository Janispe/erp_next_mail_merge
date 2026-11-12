"""Native geometry regression with synthetic PDFs; no browser/site connection."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from frappe.utils.pdf_generator.browser import Browser
from frappe.utils.pdf_generator.pdf_merge import PDFTransformer
from mail_merge.mail_merge.utils.frappe_chrome_footer_patch import apply

class TestNativeGeometry(unittest.TestCase):
    @staticmethod
    def pdf(height, pages):
        writer=PdfWriter()
        for _ in range(pages):
            page=writer.add_blank_page(width=595.27559,height=height*72)
            stream=DecodedStreamObject();stream.set_data(b'q 0 0 m 1 1 l S Q')
            page[NameObject('/Contents')]=writer._add_object(stream)
        buf=io.BytesIO();writer.write(buf);buf.seek(0)
        return PdfReader(buf)

    def test_two_page_a4_with_every_header_footer_combination(self):
        with patch.object(frappe,'__version__','16.56.0'):
            apply()
        for header,footer in [(False,False),(True,False),(False,True),(True,True)]:
            with self.subTest(header=header,footer=footer):
                b=Browser.__new__(Browser)
                b.options={'page-height':1122.519685,'page-width':793.700787,'margin-bottom':'40mm','margin-top':'15mm'}
                b._parse_pdf_options_from_html=lambda:None;b._set_default_page_size=lambda:None
                def page():return SimpleNamespace(options={},set_device_metrics=lambda **kw:None,get_element_height=lambda:24)
                b.body_page=page();b.header_page=page() if header else None;b.footer_page=page() if footer else None
                b.header_height=b.footer_height=0;b.is_print_designer=False
                b.prepare_options_for_pdf()
                b.body_pdf=self.pdf(b.body_page.options['paperHeight'],2)
                if header:b.header_pdf=self.pdf(b.header_page.options['paperHeight'],1);b.is_header_dynamic=False
                if footer:b.footer_pdf=self.pdf(b.footer_page.options['paperHeight'],1);b.is_footer_dynamic=False
                output=PDFTransformer(b).transform_pdf()
                reader=PdfReader(io.BytesIO(output)) if isinstance(output,bytes) else output
                self.assertEqual(len(reader.pages),2)
                for p in reader.pages:
                    self.assertAlmostEqual(float(p.mediabox.height),841.89,delta=2)
                    self.assertAlmostEqual(float(p.mediabox.width),595.28,delta=2)
