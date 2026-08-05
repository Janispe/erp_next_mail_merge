import unittest
from unittest.mock import patch

import frappe

from mail_merge.mail_merge.doctype.serienbrief_vorlage import serienbrief_vorlage


class TestSerienbriefVorlage(unittest.TestCase):
	def test_placeholder_exact_rule_wins_over_wildcard(self):
		rules = [
			{"pattern": "objekt.*", "visibility": "Deaktiviert"},
			{"pattern": "objekt.wohnung.name", "visibility": "Standard"},
		]
		rule = serienbrief_vorlage._matching_placeholder_rule("objekt.wohnung.name", rules)
		self.assertEqual(rule["visibility"], "Standard")

	def test_placeholder_tree_separates_direct_and_linked_fields(self):
		profile = {
			"direkte_felder_standard": True,
			"nicht_konfigurierte_pfade": "Erweitert",
			"rules": [],
		}
		node = {
			"label": "Wohnung → Wohnung",
			"token": serienbrief_vorlage._ph("objekt.wohnung.name"),
			"type": "Link",
			"children": [
				{
					"label": "Straße",
					"token": serienbrief_vorlage._ph("objekt.wohnung.strasse"),
					"type": "Data",
					"children": [],
				}
			],
		}
		standard = serienbrief_vorlage._filter_placeholder_node(
			node, "objekt", "Iterationsobjekt: Mietvertrag", 0, profile, "Standard"
		)
		advanced = serienbrief_vorlage._filter_placeholder_node(
			node, "objekt", "Iterationsobjekt: Mietvertrag", 0, profile, "Erweitert"
		)
		self.assertTrue(standard["token"])
		self.assertEqual(standard["children"], [])
		self.assertEqual(advanced["token"], "")
		self.assertEqual(len(advanced["children"]), 1)

	def test_placeholder_rule_can_disable_path_pattern(self):
		profile = {
			"direkte_felder_standard": True,
			"nicht_konfigurierte_pfade": "Erweitert",
			"rules": [{"pattern": "objekt.*.modified_by", "visibility": "Deaktiviert"}],
		}
		node = {
			"label": "Geändert von",
			"token": serienbrief_vorlage._ph("objekt.wohnung.modified_by"),
			"type": "Link",
			"children": [],
		}
		self.assertIsNone(
			serienbrief_vorlage._filter_placeholder_node(
				node, "objekt", "Iterationsobjekt: Mietvertrag", 1, profile, "Standard"
			)
		)
		self.assertIsNone(
			serienbrief_vorlage._filter_placeholder_node(
				node, "objekt", "Iterationsobjekt: Mietvertrag", 1, profile, "Erweitert"
			)
		)
		self.assertIsNone(
			serienbrief_vorlage._filter_placeholder_node(
				node, "objekt", "Iterationsobjekt: Mietvertrag", 1, profile, "Alle"
			)
		)

	def test_placeholder_all_mode_contains_standard_and_advanced(self):
		profile = {
			"direkte_felder_standard": True,
			"nicht_konfigurierte_pfade": "Erweitert",
			"rules": [],
		}
		node = {
			"label": "Wohnung → Wohnung",
			"token": serienbrief_vorlage._ph("objekt.wohnung.name"),
			"type": "Link",
			"children": [
				{
					"label": "Straße",
					"token": serienbrief_vorlage._ph("objekt.wohnung.strasse"),
					"type": "Data",
					"children": [],
				}
			],
		}
		all_fields = serienbrief_vorlage._filter_placeholder_node(
			node, "objekt", "Iterationsobjekt: Mietvertrag", 0, profile, "Alle"
		)
		self.assertTrue(all_fields["token"])
		self.assertEqual(len(all_fields["children"]), 1)

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
