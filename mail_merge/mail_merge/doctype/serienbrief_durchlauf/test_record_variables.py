import json
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import frappe

from mail_merge.mail_merge.doctype.serienbrief_durchlauf import serienbrief_durchlauf as core
from mail_merge.mail_merge.utils.render_inputs import input_fields

RECORDS = {
	("Contact", "K1"): {"first_name": "Raúl", "last_name": "Carbajosa Niehoff", "address": "ADDR-1"},
	("Contact", "K2"): {"first_name": "Inga", "last_name": "Peters", "address": "ADDR-2"},
	("Address", "ADDR-1"): {"address_line1": "Brandenburgische Straße 38", "pincode": "10707", "city": "Berlin"},
	("Address", "ADDR-2"): {"address_line1": "Tristanstr. 4", "pincode": "14109", "city": "Berlin"},
}
LINKS = {"Contact": {"address": "Address"}, "Address": {}}


class FakeMeta:
	def __init__(self, doctype):
		self.links = LINKS.get(doctype, {})

	def get_field(self, fieldname):
		target = self.links.get(fieldname)
		return frappe._dict(fieldname=fieldname, fieldtype="Link", options=target) if target else None


def record(doctype, name):
	return frappe._dict(doctype=doctype, name=name, **RECORDS[(doctype, name)])


class RecordFixtures(unittest.TestCase):
	"""Gemockte Kontakte/Adressen mit Link-Metadaten; keine Site-Daten."""

	def setUp(self):
		self.readable = True
		self.get_doc = Mock(side_effect=record)
		stack = ExitStack()
		self.addCleanup(stack.close)
		stack.enter_context(patch.object(frappe, "get_meta", side_effect=FakeMeta))
		stack.enter_context(patch.object(frappe, "get_doc", self.get_doc))
		stack.enter_context(patch.object(frappe, "get_cached_doc", side_effect=record))
		stack.enter_context(patch.object(frappe.db, "exists", side_effect=lambda dt, name: (dt, name) in RECORDS))
		stack.enter_context(patch.object(frappe, "has_permission", side_effect=lambda *a, **k: self.readable))
		stack.enter_context(patch.object(core, "_get_block_default_path_map", return_value={"var": "objekt.mieter[]", "address": "objekt.kunde.briefanschrift"}))

	def run_context(self, common=None):
		run = core.SerienbriefDurchlauf.__new__(core.SerienbriefDurchlauf)
		run.__dict__.update(date="2026-09-30", title="Test", name="RUN", iteration_doctype="Mietvertrag", vorlage=None, variablen_werte=json.dumps({k: {"value": v} for k, v in (common or {}).items()}))
		row = frappe._dict(_iteration_doc=frappe._dict(name="MV-1"), _iteration_variablen_werte=None)
		return run, run._build_context(row, 1)

	def template(self, werte=None, variable_type="Doctype"):
		return frappe._dict(
			title="Antwort", name="T", textbausteine=[],
			variables=[frappe._dict(variable="anwalt", variable_type=variable_type, reference_doctype="Contact", optional=0),
				frappe._dict(variable="hinweis", variable_type="Text", optional=1)],
			variablen_werte=json.dumps(werte or {}),
		)


class TestRecordVariables(RecordFixtures):
	"""Doctype-Variablen mit fest gewähltem Datensatz: laden, Links folgen, Vorrang, Rechte."""

	def test_fixed_template_record_is_loaded_and_follows_links(self):
		run, context = self.run_context()
		run._apply_template_variables(context, self.template({"anwalt": {"value": "K1"}}))
		self.assertEqual(context.anwalt.first_name, "Raúl")
		self.assertEqual(core._resolve_value_path("anwalt.address.city", context), "Berlin")
		self.get_doc.assert_called_once_with("Contact", "K1")

	def test_run_value_replaces_template_record_and_path(self):
		run, context = self.run_context({"anwalt": "K2"})
		run._apply_template_variables(context, self.template({"anwalt": {"value": "K1", "path": "objekt.kunde"}}))
		self.assertEqual(context.anwalt.last_name, "Peters")
		# Der Name aus den Overrides verdrängt den geladenen Datensatz nicht.
		core._apply_context_overrides(context, self.template(), run)
		self.assertEqual(core._resolve_value_path("anwalt", context).last_name, "Peters")

	def test_record_list_accepts_names_and_json(self):
		run, context = self.run_context()
		template = self.template({"anwalt": {"value": '["K1", "K2"]'}}, variable_type="Doctype Liste")
		run._apply_template_variables(context, template)
		self.assertEqual([c.first_name for c in context.anwalt], ["Raúl", "Inga"])

	def test_single_record_rejects_several_names(self):
		run, context = self.run_context()
		with self.assertRaises(frappe.ValidationError):
			run._apply_template_variables(context, self.template({"anwalt": {"value": ["K1", "K2"]}}))

	def test_missing_or_unreadable_record_is_not_loaded(self):
		run, context = self.run_context()
		with self.assertRaises(frappe.DoesNotExistError):
			run._apply_template_variables(context, self.template({"anwalt": {"value": "UNBEKANNT"}}))
		self.readable = False
		with self.assertRaises(frappe.PermissionError):
			run._apply_template_variables(context, self.template({"anwalt": {"value": "K1"}}))
		self.get_doc.assert_not_called()

	def test_block_paths_can_start_at_template_record(self):
		# Briefkopf an den Anwalt: Standardpfade zeigen auf den Mieter, die Vorlage biegt sie um.
		run, context = self.run_context()
		run._apply_template_variables(context, self.template({"anwalt": {"value": "K1"}}))
		block = frappe._dict(name="Briefkopf", title="Briefkopf", variables=[
			frappe._dict(variable="var", variable_type="Doctype Liste", reference_doctype="Contact", optional=0),
			frappe._dict(variable="address", variable_type="Doctype", reference_doctype="Address", optional=0)])
		row = frappe._dict(pfad_zuordnung=json.dumps({"var": "anwalt", "address": "anwalt.address"}))
		result = run._build_block_context(context, block, row, "briefkopf")
		self.assertEqual([c.last_name for c in result["var"]], ["Carbajosa Niehoff"])
		self.assertEqual(result.address.address_line1, "Brandenburgische Straße 38")

	def test_fixed_block_record_wins_over_standard_path(self):
		run, context = self.run_context()
		block = frappe._dict(name="Briefkopf", title="Briefkopf", variables=[
			frappe._dict(variable="address", variable_type="Doctype", reference_doctype="Address", optional=0)])
		row = frappe._dict(variablen_werte=json.dumps({"address": {"value": "ADDR-2"}}))
		result = run._build_block_context(context, block, row, "briefkopf")
		self.assertEqual(result.address.address_line1, "Tristanstr. 4")

	def test_input_fields_list_record_variables_only_on_request(self):
		template = self.template({"anwalt": {"value": "K1"}})
		self.assertEqual([f["name"] for f in input_fields(template)], ["datum", "hinweis"])
		fields = {f["name"]: f for f in input_fields(template, include_records=True)}
		self.assertEqual(fields["anwalt"]["type"], "Doctype")
		self.assertEqual(fields["anwalt"]["reference_doctype"], "Contact")
		self.assertEqual(fields["anwalt"]["default"], "K1")
		self.assertTrue(fields["anwalt"]["required"])
		with_path = self.template({"anwalt": {"path": "objekt.kunde"}})
		self.assertFalse({f["name"]: f for f in input_fields(with_path, include_records=True)}["anwalt"]["required"])


class FakeTemplateDoc(frappe._dict):
	def set(self, key, value):
		self[key] = value


class TestRecordVariablesInEditor(RecordFixtures):
	"""Editor-Speichern und Split-Vorschau behandeln den festen Datensatz wie der Durchlauf."""

	def test_editor_saves_record_as_value_and_path_otherwise(self):
		from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import _apply_editor_variables

		doc = FakeTemplateDoc(variables=[])
		_apply_editor_variables(doc, json.dumps([
			{"variable": "anwalt", "type": "Doctype", "reference_doctype": "Contact", "value": " K1 ", "path": "objekt.kunde", "source": "record"},
			{"variable": "empfaenger", "type": "Doctype Liste", "reference_doctype": "Contact", "value": [], "path": "objekt.mieter"},
		]))
		self.assertEqual(json.loads(doc.variablen_werte), {"anwalt": {"value": "K1"}})
		self.assertEqual(json.loads(doc.pfad_zuordnung), {"empfaenger": "objekt.mieter"})
		self.assertEqual([row["reference_doctype"] for row in doc.variables], ["Contact", "Contact"])

	def test_split_preview_loads_record_and_never_uses_its_name_as_text(self):
		from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import _preview_defaults_for_template

		defaults = _preview_defaults_for_template(self.template({"anwalt": {"value": "K1"}}), base_context={})
		self.assertEqual(defaults["anwalt"].first_name, "Raúl")
		self.readable = False
		defaults = _preview_defaults_for_template(self.template({"anwalt": {"value": "K1"}}), base_context={})
		self.assertNotIn("anwalt", defaults)
