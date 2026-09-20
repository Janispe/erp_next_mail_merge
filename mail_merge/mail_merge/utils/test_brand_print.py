import unittest
from unittest.mock import patch
import frappe
from mail_merge.mail_merge.utils.brand_print import apply_print_saving_brand_assets


class TestGenericPrintTransform(unittest.TestCase):
    def test_no_application_hook_leaves_html_unchanged(self):
        html = '<p><img src="/files/logo.svg">Text</p>'
        with patch.object(frappe, "get_hooks", return_value=[]):
            self.assertEqual(apply_print_saving_brand_assets(html, True), html)
