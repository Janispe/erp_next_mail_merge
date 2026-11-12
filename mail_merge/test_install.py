"""Migration regression tests isolated from actual site Print Format records."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mail_merge import install


class TestSerienbriefPrintFormatMigration(unittest.TestCase):
    def setUp(self):
        margins = patch.object(
            install, "get_serienbrief_margins", return_value=install.SERIENBRIEF_MARGIN_DEFAULTS
        )
        margins.start()
        self.addCleanup(margins.stop)

    def existing_format(self, html, *, damaged=True):
        return SimpleNamespace(
            html=html,
            doc_type="Customer" if damaged else "Serienbrief Dokument",
            print_format_type="JS" if damaged else "Jinja",
            custom_format=0 if damaged else 1,
            disabled=1 if damaged else 0,
            save=Mock(),
        )

    def assert_metadata(self, doc):
        self.assertEqual(doc.doc_type, "Serienbrief Dokument")
        self.assertEqual(doc.print_format_type, "Jinja")
        self.assertEqual(doc.custom_format, 1)
        self.assertEqual(doc.disabled, 0)

    def test_nonempty_html_preserved_while_metadata_repaired(self):
        for html in ('  <main>Individuell {{ doc.name }}</main>\n', '<p>Old default</p>'):
            with self.subTest(html=html), patch.object(install, "frappe") as frappe:
                doc = self.existing_format(html)
                frappe.db.exists.return_value = True
                frappe.get_doc.return_value = doc
                for _ in range(2):
                    install.ensure_serienbrief_dokument_print_format()
                self.assertEqual(doc.html, html)  # Exact bytes, including whitespace.
                self.assert_metadata(doc)
                doc.save.assert_called_once_with(ignore_permissions=True)
                frappe.log_error.assert_not_called()

    def test_empty_html_populated_and_metadata_repaired_once(self):
        for html in (None, "", " \t\n "):
            with self.subTest(html=html), patch.object(install, "frappe") as frappe:
                doc = self.existing_format(html)
                frappe.db.exists.return_value = True
                frappe.get_doc.return_value = doc
                install.ensure_serienbrief_dokument_print_format()
                generated = doc.html
                install.ensure_serienbrief_dokument_print_format()
                self.assertIn("{{ (doc.html or '') | safe }}", generated)
                self.assertIn("render_document_footer_html(doc)", generated)
                self.assertEqual(doc.html, generated)
                self.assert_metadata(doc)
                doc.save.assert_called_once_with(ignore_permissions=True)
                frappe.log_error.assert_not_called()

    def test_existing_usable_format_never_saved(self):
        with patch.object(install, "frappe") as frappe:
            doc = self.existing_format("<p>Site layout</p>", damaged=False)
            frappe.db.exists.return_value = True
            frappe.get_doc.return_value = doc
            for _ in range(2):
                install.ensure_serienbrief_dokument_print_format()
            doc.save.assert_not_called()
            frappe.log_error.assert_not_called()

    def test_missing_format_created_once(self):
        with patch.object(install, "frappe") as frappe:
            frappe.db.exists.side_effect = [True, False, True, True]
            created = self.existing_format(None, damaged=False)
            insertion = Mock()
            def get_doc(*args):
                if isinstance(args[0], dict):
                    created.html = args[0]["html"]
                    return SimpleNamespace(insert=insertion)
                return created
            frappe.get_doc.side_effect = get_doc
            for _ in range(2):
                install.ensure_serienbrief_dokument_print_format()
            fields = frappe.get_doc.call_args_list[0].args[0]
            self.assertEqual(fields["name"], "Serienbrief Dokument")
            self.assertEqual(fields["doc_type"], "Serienbrief Dokument")
            self.assertEqual(fields["print_format_type"], "Jinja")
            self.assertEqual(fields["custom_format"], 1)
            self.assertIn("{{ (doc.html or '') | safe }}", fields["html"])
            insertion.assert_called_once_with(ignore_permissions=True)
            created.save.assert_not_called()
            frappe.log_error.assert_not_called()

    def test_missing_doctype_does_not_create_format(self):
        with patch.object(install, "frappe") as frappe:
            frappe.db.exists.return_value = False
            install.ensure_serienbrief_dokument_print_format()
            frappe.get_doc.assert_not_called()
