import json
import unittest
from contextlib import ExitStack, nullcontext
from io import BytesIO
from unittest.mock import Mock, patch

import frappe

from mail_merge.mail_merge.utils import letter_composer as api
from mail_merge.mail_merge.utils.letter_composer_state import input_fingerprint


class TestInputSnapshots(unittest.TestCase):
	def test_input_fingerprint_detects_values_and_recipients_but_not_status(self):
		run = frappe._dict(
			vorlage="V",
			date="2026-09-18",
			title="Brief",
			iteration_doctype="Beispieldatensatz",
			variablen_werte='{"datum":{"value":"A"}}',
			iteration_objekte=[],
		)
		initial = input_fingerprint(run)
		run.status = "Generiert"
		run.name = "NEW-NAME"
		self.assertEqual(initial, input_fingerprint(run))
		run.variablen_werte = '{"datum":{"value":"B"}}'
		self.assertNotEqual(initial, input_fingerprint(run))
		before = input_fingerprint(run)
		run.iteration_objekte = [
			frappe._dict(objekt="MV", iteration_doctype="Beispieldatensatz", variablen_werte="{}")
		]
		self.assertNotEqual(before, input_fingerprint(run))
		before = input_fingerprint(run)
		run.iteration_objekte[0].variablen_werte = json.dumps(
			{"hinweistext": {"value": "Text"}}
		)
		self.assertNotEqual(before, input_fingerprint(run))


class TestComposerValidation(unittest.TestCase):
	def test_required_fields_and_false_zero(self):
		for kind, value in (("Bool", False), ("Zahl", 0)):
			field = {"name": "v", "label": "Wert", "required": True, "type": kind}
			self.assertEqual(api.validate_value(value, field), value)
		field = {"name": "termin", "label": "Termin", "required": True, "type": "Datum"}
		with self.assertRaisesRegex(ValueError, "Termin fehlt"):
			api.validate_value("", field)
		for invalid in ("2026-02-30", "18.09.2026", 3):
			with self.assertRaises(ValueError):
				api.validate_value(invalid, field)

	def test_no_html_or_jinja_and_safe_text_escaping(self):
		for value in ("<b>x</b>", "{{ objekt.name }}", "&lt;script&gt;", "{% x %}", "x" * 4001):
			with self.subTest(value=value[:20]), self.assertRaises(ValueError):
				api.text_value(value)
		self.assertEqual(
			api.validate_value("A & B", {"label": "Text", "required": False, "type": "Text"}),
			"A &amp; B",
		)

	def test_context_and_path_inputs_are_listed_with_template_variables(self):
		template = frappe._dict(
			variables=[
				frappe._dict(variable="auto", variable_type="Text", optional=0),
				frappe._dict(variable="hinweis", variable_type="Text", optional=1, label="Hinweis"),
			],
			variablen_werte=json.dumps(
				{"auto": {"path": "objekt.name"}, "hinweis": {"value": "Standard"}}
			),
		)
		fields = api.fields_for(template)
		self.assertEqual([f["name"] for f in fields], ["datum", "auto", "hinweis"])
		self.assertFalse(fields[-1]["required"])
		self.assertEqual(fields[-1]["default"], "Standard")

	def test_failed_preview_cannot_be_saved(self):
		payload = {"ready": False}
		with (
			patch.object(api, "can_create"),
			patch.object(api, "cache_key", return_value="key"),
			patch.object(api, "prepared", return_value=payload),
			patch.object(frappe, "cache", Mock()) as cache,
			patch.object(api, "_", side_effect=lambda s: s),
			patch.object(frappe, "throw", side_effect=frappe.ValidationError),
			patch.object(frappe, "get_doc") as get_doc,
		):
			cache.lock.return_value = nullcontext()
			with self.assertRaises(frappe.ValidationError):
				api.save("token")
			get_doc.assert_not_called()

	def test_missing_create_permission_blocks_preview(self):
		with patch.object(frappe, "has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				api.preview({})

	def test_preview_keeps_common_values_shared_and_blocks_missing_individual_value(self):
		from pypdf import PdfWriter

		writer = PdfWriter()
		writer.add_blank_page(width=595, height=842)
		stream = BytesIO()
		writer.write(stream)
		run = Mock(iteration_objekte=[])
		run.append.side_effect = lambda table, row: run.iteration_objekte.append(frappe._dict(row))
		run._render_segments_pdf_bytes.return_value = stream.getvalue()
		run._render_segments_preview_pages.return_value = ["<p>Vorschau</p>"]
		run._wrap_html_fragment.side_effect = lambda value: value
		template = frappe._dict(name="V", title="Brief", haupt_verteil_objekt="Beispieldatensatz")
		field = {"name": "termin", "label": "Termin", "type": "Datum", "required": True, "default": None}
		with (
			patch.object(api, "can_create"),
			patch.object(api, "template_snapshot", return_value=(template, "v1")),
			patch.object(api, "fields_for", return_value=[field]),
			patch.object(api, "read", side_effect=lambda dt, name: frappe._dict(name=name, modified="v1")),
			patch.object(api, "cache_key", return_value="test-cache"),
			patch.object(frappe, "cache", Mock()) as cache,
			patch.object(frappe, "get_doc", return_value=run),
		):
			result = api.preview({
				"template": "V", "revision": "v1", "date": "2026-09-18",
				"recipients": ["MV-1", "MV-2"], "values": {"termin": "2026-10-06"},
				"individual": {"MV-2": {"values": {"termin": ""}}},
			})
			self.assertFalse(result["ready"])
			self.assertEqual([c["status"] for c in result["checks"]], ["ready", "missing"])
			self.assertNotIn("termin", json.loads(run.iteration_objekte[0].variablen_werte))
			self.assertEqual(json.loads(run.variablen_werte)["termin"]["value"], "2026-10-06")
			self.assertEqual(len(cache.set_value.call_args.args[1]["outputs"]), 1)
			self.assertFalse(cache.set_value.call_args.args[1]["ready"])


class TestComposerSave(unittest.TestCase):
	def setUp(self):
		self.stack = ExitStack()
		self.addCleanup(self.stack.close)
		def replace(obj, name, **kwargs):
			return self.stack.enter_context(patch.object(obj, name, **kwargs))
		self.data = {
			"ready": True,
			"run": {"name": "SBDL-BRIEF-test", "vorlage": "V", "iteration_doctype": "Beispieldatensatz"},
			"revision": "v1", "targets": {"MV-1": "unchanged"},
			"outputs": [{"recipient": "MV-1", "pdf": b"exact-preview-pdf", "html": "<p>Geprüft</p>", "values": "{}", "pages": 1}],
		}
		replace(api, "can_create")
		replace(api, "cache_key", return_value="test-key")
		replace(api, "prepared", return_value=self.data)
		replace(api, "input_fingerprint", return_value="fingerprint")
		replace(api, "_", side_effect=lambda s: s)
		replace(frappe, "throw", side_effect=frappe.ValidationError)
		self.cache = replace(frappe, "cache", new=Mock())
		self.cache.lock.return_value = nullcontext()
		self.db = replace(frappe, "db", new=Mock())
		self.db.exists.return_value = False
		self.template = replace(api, "template_snapshot", return_value=(None, "v1"))
		self.read = replace(api, "read", return_value=frappe._dict(modified="unchanged"))
		self.run = Mock(vorlage="V", kategorie="K", date="2026-09-18", iteration_doctype="Beispieldatensatz")
		self.document = Mock(doctype="Serienbrief Dokument")
		self.document.name = "DOC-1"
		self.document.insert.return_value = self.document
		self.file = Mock(file_url="/private/files/brief.pdf")
		self.file.insert.return_value = self.file
		self.get_doc = replace(frappe, "get_doc", side_effect=[self.run, self.document, self.file])

	def test_save_persists_exact_preview_bytes_and_fingerprint(self):
		self.assertEqual(api.save("token"), {"docname": "SBDL-BRIEF-test"})
		file_payload = self.get_doc.call_args_list[2].args[0]
		self.assertEqual(file_payload["content"], b"exact-preview-pdf")
		self.assertEqual(file_payload["is_private"], 1)
		self.assertEqual(file_payload["attached_to_name"], "DOC-1")
		self.run.insert.assert_called_once_with(set_name="SBDL-BRIEF-test")
		summary = json.loads(self.run.db_set.call_args.args[0]["run_summary"])
		self.assertEqual(summary["input_fingerprint"], "fingerprint")
		self.db.commit.assert_called_once()
		self.db.rollback.assert_not_called()

	def test_changed_template_blocks_all_writes(self):
		self.template.return_value = (None, "v2")
		with self.assertRaises(frappe.ValidationError):
			api.save("token")
		self.get_doc.assert_not_called()

	def test_changed_recipient_blocks_all_writes(self):
		self.read.return_value.modified = "changed"
		with self.assertRaises(frappe.ValidationError):
			api.save("token")
		self.get_doc.assert_not_called()

	def test_file_failure_rolls_back_without_committing_partial_run(self):
		self.file.insert.side_effect = RuntimeError("storage unavailable")
		with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
			api.save("token")
		self.db.rollback.assert_called_once()
		self.db.commit.assert_not_called()

	def test_retry_returns_existing_owned_run_without_writes(self):
		self.db.exists.return_value = True
		self.read.return_value.owner = "test-user"
		with patch.object(frappe, "session", frappe._dict(user="test-user")):
			self.assertEqual(api.save("token"), {"docname": "SBDL-BRIEF-test", "reused": True})
		self.get_doc.assert_not_called()
