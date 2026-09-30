import json

import frappe
from frappe.tests import IntegrationTestCase

from mail_merge.mail_merge.doctype.serienbrief_vorlage import serienbrief_vorlage
from mail_merge.mail_merge.utils import footer
from mail_merge.mail_merge.utils.textbaustein_versions import render_version_refs, template_at_version


class TestDurchlaufMitVorlagenversion(IntegrationTestCase):
	"""Ein Durchlauf kann Briefe aus einer alten Vorlagenversion erzeugen."""

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		if not frappe.db.exists("Serienbrief Kategorie", "Versionstest"):
			frappe.get_doc({"doctype": "Serienbrief Kategorie", "title": "Versionstest"}).insert(
				ignore_permissions=True
			)
		self.block = frappe.get_doc(
			{
				"doctype": "Serienbrief Textbaustein",
				"title": f"Gruss {self.suffix}",
				"content_type": "Textbaustein (Rich Text)",
				"text_content": "<p>Gruss alt</p>",
			}
		).insert(ignore_permissions=True)
		self.template = frappe.get_doc(
			{
				"doctype": "Serienbrief Vorlage",
				"title": f"Brief {self.suffix}",
				"kategorie": "Versionstest",
				"haupt_verteil_objekt": "User",
				"content_type": "Textbaustein (Rich Text)",
				"content": f'<p>Brief alt</p><p>{{{{ baustein("{self.block.name}") }}}}</p>',
			}
		).insert(ignore_permissions=True)
		self.old_version = self._latest_template_version()

		self.block.reload()
		self.block.text_content = "<p>Gruss neu</p>"
		self.block.save(ignore_permissions=True)
		self.template.reload()
		self.template.content = f'<p>Brief neu</p><p>{{{{ baustein("{self.block.name}") }}}}</p>'
		self.template.flags.force_template_version = True
		self.template.save(ignore_permissions=True)

	def _latest_template_version(self):
		return frappe.get_all(
			"Serienbrief Vorlagenversion",
			filters={"vorlage": self.template.name},
			order_by="version_number desc",
			pluck="name",
			limit=1,
		)[0]

	def _run(self, version=None):
		return frappe.get_doc(
			{
				"doctype": "Serienbrief Durchlauf",
				"title": f"Lauf {self.suffix}",
				"vorlage": self.template.name,
				"vorlagenversion": version,
				"kategorie": "Versionstest",
				"iteration_doctype": "User",
				"iteration_objekte": [{"iteration_doctype": "User", "objekt": "Administrator"}],
			}
		)

	def test_template_at_version_reproduces_content_and_blocks_of_that_time(self):
		template = template_at_version(self.template.name, self.old_version)
		self.assertIn("Brief alt", template.content)
		self.assertEqual(template.flags.textbaustein_snapshots[self.block.name].text_content, "<p>Gruss alt</p>")
		# Die gespeicherte Vorlage bleibt unberuehrt.
		self.assertIn("Brief neu", frappe.db.get_value("Serienbrief Vorlage", self.template.name, "content"))

	def test_run_renders_old_version_and_default_run_renders_current(self):
		html_old = self._run(self.old_version)._render_full_html()
		self.assertIn("Brief alt", html_old)
		self.assertIn("Gruss alt", html_old)
		self.assertNotIn("neu", html_old)

		html_current = self._run()._render_full_html()
		self.assertIn("Brief neu", html_current)
		self.assertIn("Gruss neu", html_current)

	def test_documents_record_the_chosen_version(self):
		refs = render_version_refs(self._run(self.old_version)._run_template())
		self.assertEqual(refs["vorlagenversion"], self.old_version)
		bill = json.loads(refs["textbaustein_versionen"])
		self.assertEqual(bill[0]["version_number"], 1)

	def test_version_of_another_template_is_rejected(self):
		other = frappe.get_doc(
			{
				"doctype": "Serienbrief Vorlage",
				"title": f"Andere {self.suffix}",
				"kategorie": "Versionstest",
				"content_type": "Textbaustein (Rich Text)",
				"content": "<p>x</p>",
			}
		).insert(ignore_permissions=True)
		foreign = frappe.get_all("Serienbrief Vorlagenversion", filters={"vorlage": other.name}, pluck="name")[0]
		with self.assertRaises(frappe.ValidationError):
			self._run(foreign).insert(ignore_permissions=True)

	def test_version_chosen_by_a_run_cannot_be_deleted(self):
		run = self._run(self.old_version)
		run.status = "Läuft"  # kein Auto-Render beim Speichern
		run.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			serienbrief_vorlage.delete_editor_version(self.template.name, self.old_version)

	def test_print_footer_follows_the_run_version_not_the_document_evidence(self):
		run = self._run(self.old_version)
		run.status = "Läuft"
		run.insert(ignore_permissions=True)
		dokument = frappe._dict(doctype="Serienbrief Dokument", durchlauf=run.name, vorlagenversion="egal")
		self.assertEqual(footer._fixed_template_version(dokument), self.old_version)
		unpinned = frappe._dict(doctype="Serienbrief Dokument", durchlauf=None, vorlagenversion="egal")
		self.assertEqual(footer._fixed_template_version(unpinned), "")
