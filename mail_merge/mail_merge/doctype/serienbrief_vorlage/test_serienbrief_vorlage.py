import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

import frappe
from frappe.utils import now_datetime

from mail_merge.mail_merge.doctype.serienbrief_vorlage import serienbrief_vorlage


class TestSerienbriefVorlage(unittest.TestCase):
	def test_split_preview_uses_durchlauf_pipeline_and_publishes_inline_outputs(self):
		from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import (
			SerienbriefDurchlauf,
		)

		durchlauf = SerienbriefDurchlauf({"doctype": "Serienbrief Durchlauf"})
		block = frappe._dict(
			name="Zaehler",
			title="Zähler",
			content_type="Textbaustein (Rich Text)",
			text_content="Mieter",
			render_position="Body",
			variables=[],
			outputs=[
				frappe._dict(
					output_name="anzahl",
					value_path="serienbrief.count",
				)
			],
		)
		template = frappe._dict(
			name="VORSCHAU-OUTPUTS",
			title="Vorschau Outputs",
			haupt_verteil_objekt="Mietvertrag",
			content_type="Textbaustein (Rich Text)",
			content=(
				'{{ baustein("Zaehler") }} '
				"{% if outputs.anzahl.anzahl < 2 %}hat{% else %}haben{% endif %}"
			),
			textbausteine=[
				frappe._dict(
					baustein="Zaehler",
					baustein_key="anzahl",
					pfad_zuordnung="",
					variablen_werte="",
				)
			],
			variables=[],
			variablen_werte="",
			pfad_zuordnung="",
			inline_baustein_pfade="{}",
			inline_baustein_werte="{}",
		)

		with patch.object(
			serienbrief_vorlage.frappe,
			"new_doc",
			return_value=durchlauf,
		), patch.object(
			serienbrief_vorlage.frappe,
			"get_cached_doc",
			return_value=block,
		), patch.object(
			serienbrief_vorlage,
			"_load_preview_profile_values",
			return_value=({}, {}),
		):
			html = serienbrief_vorlage._build_split_preview_html(template)

		self.assertIn("Mieter", html)
		self.assertIn("hat", html)
		self.assertNotIn("Vorlagenfehler", html)

	def test_only_expendable_intermediate_version_can_be_deleted(self):
		version = frappe._dict(
			name="VERSION-2",
			source="Gespeichert",
			is_protected=0,
		)
		self.assertEqual(
			serienbrief_vorlage._version_delete_block_reason(
				version,
				latest_name="VERSION-3",
				first_name="VERSION-1",
				referenced_names=set(),
			),
			"",
		)

	def test_version_delete_protects_history_anchors(self):
		cases = (
			(frappe._dict(name="VERSION-3", source="Gespeichert", is_protected=0), "VERSION-3", "VERSION-1", set(), "aktuelle Stand"),
			(frappe._dict(name="VERSION-1", source="Ausgangsstand", is_protected=0), "VERSION-3", "VERSION-1", set(), "Ausgangsstand"),
			(frappe._dict(name="VERSION-2", source="Gespeichert", is_protected=1), "VERSION-3", "VERSION-1", set(), "Geschützte"),
			(frappe._dict(name="VERSION-2", source="Gespeichert", is_protected=0), "VERSION-3", "VERSION-1", {"VERSION-2"}, "Ursprung"),
		)
		for version, latest, first, referenced, message in cases:
			with self.subTest(message=message):
				reason = serienbrief_vorlage._version_delete_block_reason(
					version,
					latest_name=latest,
					first_name=first,
					referenced_names=referenced,
				)
				self.assertIn(message, reason)

	def test_explicit_new_version_forces_checkpoint(self):
		doc = frappe._dict(
			name="VORLAGE-1",
			title="VORLAGE-1",
			content_type="Textbaustein (Rich Text)",
			content="Aktuell",
			flags=frappe._dict(),
			modified="2026-08-06 00:00:00",
		)
		doc.save = Mock()
		with patch.object(
			serienbrief_vorlage.frappe,
			"has_permission",
			return_value=True,
		), patch.object(
			serienbrief_vorlage.frappe,
			"get_doc",
			return_value=doc,
		), patch.object(
			serienbrief_vorlage,
			"pretty_date",
			return_value="gerade eben",
		):
			serienbrief_vorlage.save_editor_template(
				name="VORLAGE-1",
				html="Aktuell",
				force_new_version=1,
			)

		doc.save.assert_called_once()
		self.assertEqual(doc.flags.version_source, "Gespeichert")
		self.assertTrue(doc.flags.force_template_version)

	def test_quick_unnamed_saves_are_coalesced(self):
		now = now_datetime()
		latest = frappe._dict(
			source="Gespeichert",
			version_label="",
			is_protected=0,
			restored_from="",
			owner="Administrator",
			creation=now - timedelta(minutes=5),
		)
		self.assertTrue(
			serienbrief_vorlage._can_coalesce_template_version(
				latest,
				source="Gespeichert",
				label="",
				restored_from="",
				force=False,
				now=now,
				user="Administrator",
			)
		)

	def test_checkpoints_and_old_saves_are_not_coalesced(self):
		now = now_datetime()
		base = {
			"source": "Gespeichert",
			"version_label": "",
			"is_protected": 0,
			"restored_from": "",
			"owner": "Administrator",
			"creation": now - timedelta(minutes=5),
		}
		for changes in (
			{"version_label": "Freigabe"},
			{"is_protected": 1},
			{"restored_from": "version-1"},
			{"creation": now - timedelta(minutes=16)},
		):
			self.assertFalse(
				serienbrief_vorlage._can_coalesce_template_version(
					frappe._dict({**base, **changes}),
					source="Gespeichert",
					label="",
					restored_from="",
					force=False,
					now=now,
					user="Administrator",
				)
			)

	def test_restore_version_only_returns_draft_without_saving(self):
		version = frappe._dict(name="VERSION-1", version_number=1, snapshot='{"content":"Alt"}')
		doc = frappe._dict(name="VORLAGE-1", content="Aktuell")
		with patch.object(
			serienbrief_vorlage.frappe,
			"has_permission",
			return_value=True,
		), patch.object(
			serienbrief_vorlage,
			"_require_template_version",
			return_value=version,
		), patch.object(
			serienbrief_vorlage,
			"_parse_version_snapshot",
			return_value={"content": "Alt"},
		), patch.object(
			serienbrief_vorlage.frappe,
			"get_doc",
			return_value=doc,
		), patch.object(
			serienbrief_vorlage,
			"_apply_template_snapshot",
		) as apply_snapshot, patch.object(
			serienbrief_vorlage,
			"_editor_template_payload",
			return_value={"id": "VORLAGE-1", "html": "Alt"},
		):
			result = serienbrief_vorlage.restore_editor_version("VORLAGE-1", "VERSION-1")

		apply_snapshot.assert_called_once_with(doc, {"content": "Alt"})
		self.assertEqual(result["restored_from_version"], "VERSION-1")
		self.assertEqual(result["restored_from_number"], 1)
		self.assertNotIn("save", doc)

	def test_save_marks_restored_origin_only_on_explicit_save(self):
		version = frappe._dict(name="VERSION-1", version_number=1)
		doc = frappe._dict(
			name="VORLAGE-1",
			title="VORLAGE-1",
			content_type="Textbaustein (Rich Text)",
			content="Aktuell",
			flags=frappe._dict(),
			modified="2026-08-06 00:00:00",
		)
		doc.save = Mock()
		with patch.object(
			serienbrief_vorlage.frappe,
			"has_permission",
			return_value=True,
		), patch.object(
			serienbrief_vorlage.frappe,
			"get_doc",
			return_value=doc,
		), patch.object(
			serienbrief_vorlage,
			"_require_template_version",
			return_value=version,
		), patch.object(
			serienbrief_vorlage,
			"pretty_date",
			return_value="gerade eben",
		):
			serienbrief_vorlage.save_editor_template(
				name="VORLAGE-1",
				html="Alt",
				restored_from_version="VERSION-1",
			)

		doc.save.assert_called_once()
		self.assertEqual(doc.flags.version_source, "Wiederherstellung")
		self.assertEqual(doc.flags.version_restored_from, "VERSION-1")
		self.assertTrue(doc.flags.force_template_version)

	def test_version_snapshot_captures_full_editor_state(self):
		doc = frappe._dict(
			title="Testvorlage",
			haupt_verteil_objekt="Mietvertrag",
			kategorie="Vertraege",
			favorite=1,
			content_type="Textbaustein (Rich Text)",
			content="<p>Hallo {{ name }}</p>",
			html_content="",
			jinja_content="",
			content_position="Nach Bausteinen",
			pfad_zuordnung='{"name":"objekt.name"}',
			variablen_werte="",
			inline_baustein_pfade="{}",
			inline_baustein_werte="{}",
			description="Interne Notiz",
			variables=[{"variable": "name", "variable_type": "Text", "idx": 1}],
			textbausteine=[{"baustein": "Briefkopf", "baustein_key": "briefkopf", "idx": 1}],
		)
		snapshot = serienbrief_vorlage._build_template_snapshot(doc)

		self.assertEqual(snapshot["content"], "<p>Hallo {{ name }}</p>")
		self.assertEqual(snapshot["variables"][0]["variable"], "name")
		self.assertEqual(snapshot["textbausteine"][0]["baustein_key"], "briefkopf")
		self.assertNotIn("parent", snapshot["variables"][0])

	def test_version_hash_is_stable_and_changes_with_content(self):
		left = {"doctype": "Serienbrief Vorlage", "schema_version": 1, "content": "A"}
		right = {"schema_version": 1, "content": "A", "doctype": "Serienbrief Vorlage"}
		changed = {**right, "content": "B"}

		self.assertEqual(
			serienbrief_vorlage._snapshot_hash(left),
			serienbrief_vorlage._snapshot_hash(right),
		)
		self.assertNotEqual(
			serienbrief_vorlage._snapshot_hash(left),
			serienbrief_vorlage._snapshot_hash(changed),
		)

	def test_version_diff_marks_removed_and_added_text(self):
		parts = serienbrief_vorlage._word_diff("Alter Vertrag", "Neuer Vertrag")
		self.assertTrue(any(part["type"] == "removed" and "Alter" in part["text"] for part in parts))
		self.assertTrue(any(part["type"] == "added" and "Neuer" in part["text"] for part in parts))

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
