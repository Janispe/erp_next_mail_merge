"""Synthetic initialization and native PDF compatibility regressions."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import frappe
from mail_merge import hooks, install
from mail_merge.mail_merge.utils import frappe_chrome_footer_patch as footer

class TestCompanionDefaults(unittest.TestCase):
    def test_link_default_deferred_until_format_exists(self):
        path = Path(__file__).parent / 'mail_merge/doctype/serienbrief_einstellungen/serienbrief_einstellungen.json'
        field = next(f for f in json.loads(path.read_text())['fields'] if f['fieldname'] == 'editor_print_format')
        self.assertFalse(field.get('default'))
        self.assertEqual(install.SERIENBRIEF_SETTINGS_DEFAULTS.get('editor_print_format'), 'Serienbrief Dokument')
        for names in [getattr(hooks, 'after_install', []), hooks.after_migrate]:
            self.assertIn('mail_merge.install.ensure_serienbrief_dokument_print_format', names)
            self.assertLess(names.index('mail_merge.install.ensure_serienbrief_dokument_print_format'), names.index('mail_merge.install.ensure_serienbrief_settings_defaults'))

    def test_explicit_settings_choice_preserved(self):
        with patch.object(install, 'frappe') as f:
            f.db.exists.return_value = True
            f.db.get_single_value.return_value = 'synthetic-choice'
            install.ensure_serienbrief_settings_defaults()
            f.db.set_single_value.assert_not_called()

    def test_native_core_method_remains_unchanged(self):
        from frappe.utils.pdf_generator.browser import Browser
        original = Browser.prepare_options_for_pdf
        with patch.object(frappe, '__version__', '16.56.0'):
            footer.apply(); footer.apply()
        self.assertIs(Browser.prepare_options_for_pdf, original)
        self.assertFalse(getattr(Browser,footer._PATCHED_FLAG,False))

    def test_legacy_workaround_remains_idempotent_below_native_fix(self):
        from frappe.utils.pdf_generator import browser
        class LegacyBrowser:
            calls=0
            def prepare_options_for_pdf(self):
                self.calls+=1
        with patch.object(frappe,'__version__','15.99.0'),patch.object(browser,'Browser',LegacyBrowser):
            footer.apply();method=LegacyBrowser.prepare_options_for_pdf;footer.apply()
            self.assertIs(LegacyBrowser.prepare_options_for_pdf,method)
            instance=LegacyBrowser();instance.prepare_options_for_pdf()
            self.assertEqual(instance.calls,1)
            self.assertTrue(getattr(LegacyBrowser,footer._PATCHED_FLAG))

    def test_empty_defaults_seeded_once(self):
        values={}
        with patch.object(install,'frappe') as f:
            f.db.exists.return_value=True
            f.db.get_single_value.side_effect=lambda dt,key: values.get(key)
            f.db.set_single_value.side_effect=lambda dt,key,value: values.__setitem__(key,value)
            install.ensure_serienbrief_settings_defaults();install.ensure_serienbrief_settings_defaults()
            self.assertEqual(values.get('editor_print_format'),'Serienbrief Dokument')
            self.assertEqual(f.db.set_single_value.call_count,len(install.SERIENBRIEF_SETTINGS_DEFAULTS))
