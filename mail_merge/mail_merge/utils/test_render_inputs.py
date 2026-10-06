import json
import unittest
from unittest.mock import patch

import frappe
from mail_merge.mail_merge.doctype.serienbrief_durchlauf import serienbrief_durchlauf as core
from mail_merge.mail_merge.utils.render_inputs import input_fields


class TestGenericRenderContext(unittest.TestCase):
	def run_context(self, common=None, individual=None):
		run = core.SerienbriefDurchlauf.__new__(core.SerienbriefDurchlauf)
		run.__dict__.update(date="2026-09-21", title="Test", name="RUN", iteration_doctype="Example", vorlage=None, variablen_werte=json.dumps({k: {"value": v} for k, v in (common or {}).items()}))
		row = frappe._dict(_iteration_doc=frappe._dict(name="ITEM", label="Aus dem Objekt"), _iteration_variablen_werte=json.dumps({k: {"value": v} for k, v in (individual or {}).items()}))
		return run, run._build_context(row, 1)

	def test_context_defaults_common_and_individual_use_one_precedence(self):
		for common, individual, expected in [({}, {}, "2026-09-21"), ({"datum": "2026-10-02"}, {}, "2026-10-02"), ({"datum": "2026-10-02"}, {"datum": "2026-11-03"}, "2026-11-03")]:
			with self.subTest(expected=expected):
				_, context = self.run_context(common, individual)
				self.assertEqual(str(core._resolve_value_path("datum", context)), expected)
				self.assertEqual(context.datum_iso, expected)
				self.assertEqual(core._resolve_value_path("objekt.label", context), "Aus dem Objekt")

	def test_arbitrary_context_values_and_empty_path_overrides(self):
		_, context = self.run_context({"thema": "Allgemein", "objekt.label": "Override"}, {"thema": "Individuell", "objekt.label": ""})
		self.assertEqual(core._resolve_value_path("thema", context), "Individuell")
		self.assertEqual(core._resolve_value_path("objekt.label", context), "")

	def test_blocks_only_receive_declared_inputs_resolved_from_parent_paths(self):
		run, context = self.run_context({"datum": "2026-10-02"}, {"datum": "2026-11-03"})
		block = frappe._dict(name="Block", title="Block", standardpfade=[], variables=[frappe._dict(variable="termin", variable_type="Datum", optional=0), frappe._dict(variable="text", variable_type="Text", optional=0)])
		row = frappe._dict(pfad_zuordnung=json.dumps({"termin": "datum", "text": "objekt.label"}))
		with patch.object(core, "_get_block_default_path_map", return_value={}):
			result = run._build_block_context(context, block, row, "block")
		self.assertNotIn("objekt", result)
		self.assertNotIn("datum", result)
		self.assertNotIn("datum_iso", result)
		self.assertNotIn("outputs", result)
		self.assertNotIn("serienbrief", result)
		self.assertEqual(str(result.termin), "2026-11-03")
		self.assertEqual(result.text, "Aus dem Objekt")

	def test_catalogue_lists_context_and_block_paths_without_template_variables(self):
		template = frappe._dict(haupt_verteil_objekt="Example", textbausteine=[frappe._dict(baustein="B")])
		block = frappe._dict(name="B", title="B", variables=[frappe._dict(variable="termin", variable_type="Datum", optional=0),frappe._dict(variable="text", variable_type="Text", optional=1)])
		with patch.object(frappe,"get_cached_doc",return_value=block), patch.object(core,"_get_block_default_path_map",return_value={"termin":"datum","text":"objekt.label"}):
			fields = input_fields(template,frappe._dict(date="2026-09-21"))
		self.assertEqual([f["name"] for f in fields], ["datum","objekt.label"])
		self.assertEqual(fields[0]["type"],"Datum")

	def test_explicit_value_can_replace_an_unresolved_template_path(self):
		run, context = self.run_context({"hinweis": "Eingesetzt"})
		template = frappe._dict(title="Example", name="T", variables=[frappe._dict(variable="hinweis", variable_type="Text")], variablen_werte=json.dumps({"hinweis": {"path": "objekt.missing"}}))
		run._apply_template_variables(context, template)
		self.assertEqual(context.hinweis, "Eingesetzt")

	def test_undeclared_parent_values_do_not_enter_empty_block(self):
		run, context = self.run_context({"thema": "Privat"})
		block = frappe._dict(name="Empty", title="Empty", variables=[])
		result = run._build_block_context(context, block, None, "empty")
		self.assertEqual(set(result), {"baustein"})

	def test_matching_input_name_still_requires_a_path(self):
		run, context = self.run_context()
		block = frappe._dict(name="Date", title="Date", variables=[frappe._dict(variable="datum", variable_type="Text", optional=1)])
		with patch.object(core, "_get_block_default_path_map", return_value={}):
			result = run._build_block_context(context, block, None, "date")
		self.assertEqual(result.datum, "")

	def test_outputs_are_explicitly_published_and_mapped_to_next_block(self):
		run, context = self.run_context()
		first = frappe._dict(name="First", title="First", variables=[frappe._dict(variable="termin", variable_type="Text")], outputs=[frappe._dict(output_name="date", value_path="termin")])
		second = frappe._dict(name="Second", title="Second", variables=[frappe._dict(variable="eingang", variable_type="Text")])
		with patch.object(core, "_get_block_default_path_map", return_value={}):
			local = run._build_block_context(context, first, frappe._dict(pfad_zuordnung='{"termin":"datum"}'), "first")
			self.assertEqual(context.outputs, {})
			run._publish_block_outputs(context, local, first, "first")
			result = run._build_block_context(context, second, frappe._dict(pfad_zuordnung='{"eingang":"outputs.first.date"}'), "second")
		self.assertEqual(str(result.eingang), "2026-09-21")
		self.assertNotIn("outputs", result)
		self.assertNotIn("termin", result)

	def test_path_override_resolves_other_source_and_preserves_zero(self):
		context = {"objekt": frappe._dict(bruttomiete=900, alternative=0), "_serienbrief_value_overrides": {"objekt.bruttomiete": {"path": "objekt.alternative"}}}
		self.assertEqual(core._resolve_value_path("objekt.bruttomiete", context), 0)
		self.assertIn("0", core._preprocess_simple_paths("{{$ objekt.bruttomiete $}}", context))

	def test_invalid_and_circular_path_overrides_fail(self):
		for mapping in [{"objekt.bruttomiete": {"path": "objekt.missing"}}, {"objekt.bruttomiete": {"path": "objekt.alternative"}, "objekt.alternative": {"path": "objekt.bruttomiete"}}]:
			with self.subTest(mapping=mapping):
				context = {"objekt": frappe._dict(bruttomiete=900, alternative=750), "_serienbrief_value_overrides": mapping}
				with self.assertRaises(frappe.ValidationError):
					core._resolve_value_path("objekt.bruttomiete", context)

	def test_catalogue_includes_direct_placeholder_paths_only_when_requested(self):
		template = frappe._dict(haupt_verteil_objekt="Example", content_type="HTML + Jinja", jinja_content="{{$ objekt.bruttomiete $}}", variables=[], textbausteine=[])
		self.assertNotIn("objekt.bruttomiete", [f["name"] for f in input_fields(template)])
		self.assertIn("objekt.bruttomiete", [f["name"] for f in input_fields(template, include_paths=True)])

	def test_individual_path_replaces_common_value_for_template_variable(self):
		run, context = self.run_context({"miete": 900})
		context["objekt"]["alternative"] = 750
		context["_serienbrief_value_overrides"]["miete"] = {"path": "objekt.alternative"}
		template = frappe._dict(title="Example", name="T", variables=[frappe._dict(variable="miete", variable_type="Zahl")], variablen_werte=json.dumps({"miete": {"path": "objekt.missing"}}))
		run._apply_template_variables(context, template)
		self.assertEqual(context.miete, 750)

	def test_save_preserves_common_and_individual_paths(self):
		row = frappe._dict(objekt="ITEM")
		doc = frappe._dict(docstatus=0, flags=frappe._dict(), iteration_objekte=[row], save=lambda **kwargs: None)
		with patch.object(frappe, "get_doc", return_value=doc), patch.object(frappe, "has_permission", return_value=True), patch.object(core, "_record_input_fields", return_value={}), patch.object(frappe.db, "commit"):
			core.set_run_variables("RUN", variables=[{"name": "objekt.bruttomiete", "value": {"path": "objekt.alternative"}}], per_recipient_overrides={"ITEM": {"objekt.bruttomiete": {"path": "objekt.individual"}, "zero": 0, "empty": "", "no": False}})
		self.assertEqual(json.loads(doc.variablen_werte)["objekt.bruttomiete"], {"value": None, "path": "objekt.alternative"})
		parsed = json.loads(row.variablen_werte)
		self.assertEqual(parsed["objekt.bruttomiete"]["path"], "objekt.individual")
		self.assertEqual(parsed["zero"]["value"], 0)
		self.assertEqual(parsed["empty"]["value"], "")
		self.assertIs(parsed["no"]["value"], False)

	def test_individual_path_wins_in_actual_render_context(self):
		run, _ = self.run_context()
		run.variablen_werte = json.dumps({"objekt.bruttomiete": {"value": 900}})
		row = frappe._dict(_iteration_doc=frappe._dict(name="ITEM", bruttomiete=1000, alternative=750), _iteration_variablen_werte=json.dumps({"objekt.bruttomiete": {"path": "objekt.alternative"}}))
		context = run._build_context(row, 1)
		self.assertEqual(core._preprocess_simple_paths("{{$ objekt.bruttomiete $}}", context), "750")

	def test_empty_override_path_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			core._parse_run_input_values({"objekt.bruttomiete": {"path": "  "}})

	def test_override_path_checks_document_read_permission(self):
		from frappe.model.document import Document
		doc = Document({"doctype": "Contact", "name": "K-1", "first_name": "Ada"})
		context = {"objekt": doc, "_serienbrief_value_overrides": {"miete": {"path": "objekt.first_name"}}}
		with patch.object(doc, "check_permission", side_effect=frappe.PermissionError) as check:
			with self.assertRaises(frappe.PermissionError):
				core._resolve_value_path("miete", context)
		check.assert_called_once_with("read")
