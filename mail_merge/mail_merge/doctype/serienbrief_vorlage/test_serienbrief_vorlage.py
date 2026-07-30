import unittest
from unittest.mock import patch

import frappe

from mail_merge.mail_merge.doctype.serienbrief_vorlage import serienbrief_vorlage


class TestSerienbriefVorlage(unittest.TestCase):
	def test_inline_preview_rejects_other_document_types(self):
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Ungültiger Dokumenttyp",
		):
			serienbrief_vorlage._load_template_doc(
				template_doc={
					"doctype": "User",
					"name": "Administrator",
				}
			)

	def test_stored_html_preview_requires_read_permission_before_render(self):
		doc = frappe._dict(
			doctype="Serienbrief Vorlage",
			name="VORLAGE-GESPERRT",
		)
		with patch.object(
			serienbrief_vorlage,
			"_load_template_doc",
			return_value=doc,
		), patch.object(
			serienbrief_vorlage.frappe,
			"has_permission",
			return_value=False,
		), patch.object(
			serienbrief_vorlage,
			"_build_raw_template_html",
		) as render, self.assertRaises(frappe.PermissionError):
			serienbrief_vorlage.render_template_preview_html(
				template=doc.name,
			)

		render.assert_not_called()

	def test_inline_pdf_preview_requires_write_permission_before_jinja_render(self):
		doc = frappe._dict(
			doctype="Serienbrief Vorlage",
			name="VORLAGE-GESPERRT",
			haupt_verteil_objekt=None,
		)
		with patch.object(
			serienbrief_vorlage,
			"_load_template_doc",
			return_value=doc,
		), patch.object(
			serienbrief_vorlage.frappe.db,
			"exists",
			return_value=True,
		), patch.object(
			serienbrief_vorlage.frappe,
			"has_permission",
			return_value=False,
		), patch.object(
			serienbrief_vorlage,
			"_build_split_preview_html",
		) as render, self.assertRaises(frappe.PermissionError):
			serienbrief_vorlage.render_template_preview_pdf(
				template_doc=doc,
				split_preview=True,
			)

		render.assert_not_called()

	def test_iteration_preview_requires_target_read_permission(self):
		template = frappe._dict(
			doctype="Serienbrief Vorlage",
			name="VORLAGE-1",
			title="Vorlage",
		)
		with patch.object(
			serienbrief_vorlage.frappe.db,
			"exists",
			return_value=True,
		), patch.object(
			serienbrief_vorlage.frappe,
			"has_permission",
			return_value=False,
		), patch.object(
			serienbrief_vorlage.frappe,
			"new_doc",
		) as new_doc, self.assertRaises(frappe.PermissionError):
			serienbrief_vorlage._render_segments_via_durchlauf(
				template,
				"Customer",
				"CUST-GESPERRT",
			)

		new_doc.assert_not_called()
