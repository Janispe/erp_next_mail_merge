import json
import unittest
from datetime import datetime
from io import BytesIO
from unittest.mock import Mock, patch

import frappe
from PyPDF2 import PdfReader, PdfWriter

from mail_merge.mail_merge.doctype.serienbrief_durchlauf import serienbrief_durchlauf as core


def pdf_with_page_width(width):
	writer = PdfWriter()
	writer.add_blank_page(width=width, height=300)
	output = BytesIO()
	writer.write(output)
	return output.getvalue()


class TestSerienbriefDurchlauf(unittest.TestCase):
	def setUp(self):
		# Real controller methods and PDF merge, isolated from site data and rendering.
		self.run = object.__new__(core.SerienbriefDurchlauf)
		self.run.__dict__.update(
			doctype="Serienbrief Durchlauf",
			name="RUN",
			title="Brief",
			docstatus=1,
			status="Generiert",
			iteration_objekte=[frappe._dict(objekt="MV-1")],
		)
		self.run.check_permission = Mock()
		self.run._ensure_dokumente = Mock(return_value=["DOC-1", "DOC-2"])
		self.run._render_dokument_with_print_format = Mock(
			side_effect=AssertionError("Must not render")
		)
		self.run._store_pdf = Mock(return_value="/files/draft.pdf")
		self.documents = {
			"DOC-1": frappe._dict(
				name="DOC-1", status="Generiert", generated_pdf_file="/private/files/1.pdf"
			),
			"DOC-2": frappe._dict(
				name="DOC-2", status="Generiert", generated_pdf_file="/private/files/2.pdf"
			),
		}
		self.pdfs = {
			"/private/files/1.pdf": pdf_with_page_width(111),
			"/private/files/2.pdf": pdf_with_page_width(222),
		}
		self.addCleanup(patch.stopall)
		self.db = patch.object(frappe, "db", Mock(), create=True).start()
		self.get_all = patch.object(frappe, "get_all", return_value=list(self.documents)).start()
		self.get_doc = patch.object(frappe, "get_doc", side_effect=self._get_doc).start()
		self.permission = patch.object(frappe, "has_permission", return_value=True).start()
		patch.object(core, "now_datetime", return_value=datetime(2026, 9, 18, 12)).start()
		self.log_error = patch.object(frappe, "log_error").start()
		patch.object(core, "_", side_effect=lambda text: text).start()
		patch.object(frappe, "throw", side_effect=lambda message: self._throw(message)).start()
		self.read_pdf = patch.object(
			core, "read_file_url_bytes", side_effect=self.pdfs.__getitem__
		).start()
		self.save_file = patch(
			"frappe.utils.file_manager.save_file",
			return_value=frappe._dict(file_url="/private/files/merged.pdf"),
		).start()
		self.render = patch.object(
			core, "get_pdf", side_effect=AssertionError("Must not render")
		).start()
		self.template = patch.object(
			frappe, "get_cached_doc", side_effect=AssertionError("Must not read current template")
		).start()

	def _get_doc(self, doctype, name):
		return self.run if doctype == "Serienbrief Durchlauf" else self.documents[name]

	@staticmethod
	def _throw(message):
		raise frappe.ValidationError(message)

	def test_download_preserves_saved_pages_and_documents_for_drafts_and_submitted_runs(self):
		for docstatus in (0, 1):
			with self.subTest(docstatus=docstatus):
				self.run.docstatus = docstatus
				self.permission.side_effect = lambda dt, permission, doc: permission == "read"
				result = core.get_merged_pdf("RUN", druck_schwarz_weiss=1)
				self.assertEqual(result, {"file_url": "/private/files/merged.pdf"})
				merged = self.save_file.call_args.args[1]
				self.assertEqual(
					[float(p.mediabox.width) for p in PdfReader(BytesIO(merged)).pages], [111, 222]
				)
				self.assertEqual(self.save_file.call_args.kwargs, {"is_private": 1})
				self.assertEqual(
					self.save_file.call_args.args[2:], ("Serienbrief Durchlauf", "RUN")
				)
		self.run._ensure_dokumente.assert_not_called()
		self.run._render_dokument_with_print_format.assert_not_called()
		self.run._store_pdf.assert_not_called()
		self.db.set_value.assert_not_called()
		self.db.exists.assert_not_called()
		self.template.assert_not_called()
		self.render.assert_not_called()
		self.assertEqual(
			self.get_all.call_args.kwargs["filters"],
			{
				"durchlauf": "RUN",
				"recreate_pending": 0,
				"docstatus": ["<", 2],
			},
		)

	def test_missing_snapshot_is_an_error_instead_of_rerendering(self):
		self.documents["DOC-2"].generated_pdf_file = ""
		self.documents["DOC-2"].html = "Old HTML must not be rendered"
		with self.assertRaisesRegex(frappe.ValidationError, "gespeicherte PDF"):
			core.get_merged_pdf("RUN")
		self.save_file.assert_not_called()
		self.run._ensure_dokumente.assert_not_called()
		self.run._render_dokument_with_print_format.assert_not_called()

	def test_missing_file_is_not_replaced_by_a_new_render(self):
		self.read_pdf.side_effect = FileNotFoundError("missing.pdf")
		with self.assertRaises(FileNotFoundError):
			core.get_merged_pdf("RUN")
		self.save_file.assert_not_called()
		self.run._ensure_dokumente.assert_not_called()

	def test_merge_skips_failed_and_skipped_recipients(self):
		for status in ("Fehler", "Übersprungen"):
			with self.subTest(status=status):
				self.documents["DOC-2"].status = status
				core.get_merged_pdf("RUN")
				merged = self.save_file.call_args.args[1]
				self.assertEqual(len(PdfReader(BytesIO(merged)).pages), 1)

	def test_no_successful_documents_does_not_create_an_empty_download(self):
		for doc in self.documents.values():
			doc.status = "Fehler"
		with self.assertRaisesRegex(frappe.ValidationError, "Keine erfolgreich"):
			core.get_merged_pdf("RUN")
		self.save_file.assert_not_called()

	def test_no_documents_does_not_trigger_generation(self):
		self.get_all.return_value = []
		with self.assertRaises(frappe.ValidationError):
			core.get_merged_pdf("RUN")
		self.run._ensure_dokumente.assert_not_called()

	def test_download_requires_read_permission(self):
		self.permission.return_value = False
		with self.assertRaises(frappe.PermissionError):
			core.get_merged_pdf("RUN")
		self.get_all.assert_not_called()
		self.save_file.assert_not_called()

	def test_legacy_pdf_endpoint_also_downloads_submitted_snapshot(self):
		self.permission.side_effect = lambda dt, permission, doc: permission == "read"
		self.assertEqual(
			core.generate_pdf("RUN", print_format="Changed format"), "/private/files/merged.pdf"
		)
		self.run._ensure_dokumente.assert_not_called()
		self.run._render_dokument_with_print_format.assert_not_called()

	def test_read_only_users_cannot_regenerate_drafts_through_either_endpoint(self):
		self.run.docstatus = 0
		self.permission.side_effect = lambda dt, permission, doc: permission == "read"
		for action in (core.generate_pdf, core.regenerate_dokumente):
			with self.subTest(action=action.__name__), self.assertRaises(frappe.PermissionError):
				action("RUN")
		self.run._ensure_dokumente.assert_not_called()

	def test_explicit_regeneration_requires_a_nonrunning_draft(self):
		for docstatus, status in ((1, "Generiert"), (2, "Generiert"), (0, "Läuft")):
			self.run.docstatus, self.run.status = docstatus, status
			for action in (
				lambda: core.generate_pdf("RUN", recreate_documents=1),
				lambda: core.regenerate_dokumente("RUN"),
			):
				with (
					self.subTest(docstatus=docstatus, status=status),
					self.assertRaises(frappe.ValidationError),
				):
					action()
		self.run._ensure_dokumente.assert_not_called()

	def test_running_or_cancelled_run_cannot_be_downloaded(self):
		for docstatus, status in ((2, "Generiert"), (0, "Läuft")):
			self.run.docstatus, self.run.status = docstatus, status
			with self.subTest(docstatus=docstatus), self.assertRaises(frappe.ValidationError):
				core.get_merged_pdf("RUN")
		self.get_all.assert_not_called()

	def test_authorized_draft_regeneration_still_works(self):
		self.run.docstatus = 0
		core.regenerate_dokumente("RUN")
		self.run._ensure_dokumente.assert_called_once_with(recreate=True, submit=False)

	def test_legacy_draft_generation_requires_write_and_keeps_custom_print_format(self):
		self.run.docstatus = 0
		with patch.object(self.run, "_build_merged_pdf", return_value=b"new pdf") as merge:
			self.assertEqual(core.generate_pdf("RUN", print_format="Custom"), "/files/draft.pdf")
			merge.assert_called_once_with(["DOC-1", "DOC-2"], print_format="Custom")
		self.run._ensure_dokumente.assert_called_once_with(
			recreate=True, submit=False, strict_variables=True
		)
		self.assertIn(
			unittest.mock.call("Serienbrief Durchlauf", "write", self.run),
			self.permission.call_args_list,
		)

	def test_submitting_regenerated_documents_requires_submit_permission(self):
		self.run.docstatus = 0
		self.permission.side_effect = lambda dt, permission, doc: permission != "submit"
		with self.assertRaises(frappe.PermissionError):
			core.regenerate_dokumente("RUN", submit_documents=1)
		self.run._ensure_dokumente.assert_not_called()

	def test_background_infrastructure_failure_still_marks_failed_and_raises(self):
		self.run._ensure_dokumente.side_effect = RuntimeError("renderer unavailable")
		with self.assertRaisesRegex(RuntimeError, "renderer unavailable"):
			core._run_durchlauf_job("RUN")
		self.db.rollback.assert_called_once()
		self.db.set_value.assert_called_once_with(
			"Serienbrief Durchlauf", "RUN", "status", "Fehlgeschlagen", update_modified=False
		)

	def test_background_and_submit_status_reflect_recipient_results(self):
		cases = [
			({"total": 2, "generated": 0, "error": 2, "skipped": 0}, "Fehlgeschlagen"),
			({"total": 2, "generated": 0, "error": 1, "skipped": 1}, "Fehlgeschlagen"),
			({"total": 2, "generated": 1, "error": 1, "skipped": 0}, "Generiert"),
			({"total": 2, "generated": 2, "error": 0, "skipped": 0}, "Generiert"),
			({"total": 2, "generated": 0, "error": 0, "skipped": 2}, "Generiert"),
		]
		self.run.docstatus = 0
		self.run.submit = Mock()
		for counts, expected in cases:
			self.run._last_run_counts = counts
			for action in (core._run_durchlauf_job, core.submit_durchlauf):
				with self.subTest(counts=counts, action=action.__name__):
					result = action("RUN")
					values = self.db.set_value.call_args.args[2]
					self.assertEqual(values["status"], expected)
					self.assertEqual(json.loads(values["run_summary"]), counts)
					self.assertEqual(values["progress"], "2/2")
					if result:
						self.assertEqual(result["status"], expected)
