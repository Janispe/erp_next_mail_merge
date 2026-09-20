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
