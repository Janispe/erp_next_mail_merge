import json

import frappe
from frappe.tests import IntegrationTestCase

# Modul statt Klasse importieren: sonst liefe die Basistestklasse hier ein zweites Mal.
from mail_merge.mail_merge.doctype.serienbrief_textbausteinversion import (
	test_serienbrief_textbausteinversion as base_tests,
)
from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import TEMPLATE_VERSION_SPEC
from mail_merge.mail_merge.utils import textbaustein_versions as tbv
from mail_merge.mail_merge.utils import versioning
from mail_merge.mail_merge.utils.textbaustein_loader import get_textbaustein
from mail_merge.mail_merge.utils.textbaustein_versions import render_version_refs, template_at_version


def _snapshots(doctype, owner_field, owner):
	return frappe.get_all(
		doctype,
		filters={owner_field: owner},
		fields=["name", "version_number", "source", "sealed", "snapshot"],
		order_by="version_number asc",
	)


class TestVersionenFestschreiben(IntegrationTestCase):
	"""Eine Version, auf die etwas verweist, wird nie mehr als Arbeitsstand aufgefrischt."""

	setUp = base_tests.TestSerienbriefTextbausteinversion.setUp
	_block = base_tests.TestSerienbriefTextbausteinversion._block
	_template = base_tests.TestSerienbriefTextbausteinversion._template
	_edit = base_tests.TestSerienbriefTextbausteinversion._edit

	def _block_versions(self, block):
		return _snapshots("Serienbrief Textbausteinversion", "textbaustein", block.name)

	def _template_versions(self, template):
		return _snapshots("Serienbrief Vorlagenversion", "vorlage", template.name)

	def _save_template(self, template, content):
		template.reload()
		template.content = content
		template.save(ignore_permissions=True)

	def test_unreferenced_working_state_is_still_coalesced(self):
		block = self._block("Frei", "<p>eins</p>")
		self._edit(block, "<p>zwei</p>")
		self._edit(block, "<p>drei</p>")

		versions = self._block_versions(block)
		self.assertEqual(len(versions), 2)
		self.assertIn("drei", versions[-1].snapshot)

	def test_fixed_block_version_keeps_its_content(self):
		block = self._block("Fixiert", "<p>eins</p>")
		self._edit(block, "<p>zwei</p>")
		template = self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')
		template.baustein_versionen = json.dumps({block.name: 2})
		template.save(ignore_permissions=True)

		self._edit(block, "<p>drei</p>")

		versions = self._block_versions(block)
		self.assertEqual([v.version_number for v in versions], [1, 2, 3])
		self.assertTrue(versions[1].sealed)
		self.assertIn("zwei", versions[1].snapshot)
		frappe.local.mail_merge_fixed_textbausteine = {}
		self.assertEqual(get_textbaustein(block.name, template=template).text_content, "<p>zwei</p>")

	def test_block_version_in_a_bill_keeps_its_content(self):
		block = self._block("Stueckliste", "<p>eins</p>")
		self._edit(block, "<p>zwei</p>")
		template = self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')
		template_version = self._template_versions(template)[-1].name
		bill = json.loads(
			frappe.db.get_value("Serienbrief Vorlagenversion", template_version, "textbaustein_versionen")
		)

		self._edit(block, "<p>drei</p>")

		referenced = frappe.get_doc("Serienbrief Textbausteinversion", bill[0]["version"])
		self.assertTrue(referenced.sealed)
		self.assertIn("zwei", referenced.snapshot)
		self.assertEqual(referenced.content_hash, bill[0]["content_hash"])

	def test_document_evidence_keeps_the_template_version(self):
		template = self._template("<p>A</p>")
		self._save_template(template, "<p>B</p>")
		evidence = render_version_refs(frappe.get_doc("Serienbrief Vorlage", template.name))["vorlagenversion"]

		self._save_template(template, "<p>C</p>")

		version = frappe.get_doc("Serienbrief Vorlagenversion", evidence)
		self.assertTrue(version.sealed)
		self.assertIn("<p>B</p>", version.snapshot)
		self.assertEqual(len(self._template_versions(template)), 3)

	def test_version_chosen_by_a_run_keeps_its_content(self):
		template = self._template("<p>A</p>")
		self._save_template(template, "<p>B</p>")
		chosen = self._template_versions(template)[-1].name
		frappe.get_doc(
			{
				"doctype": "Serienbrief Durchlauf",
				"title": f"Lauf {self.suffix}",
				"vorlage": template.name,
				"vorlagenversion": chosen,
				"kategorie": "Versionstest",
				"status": "Läuft",
			}
		).insert(ignore_permissions=True)

		self._save_template(template, "<p>C</p>")

		self.assertIn("<p>B</p>", template_at_version(template.name, chosen).content)

	def test_proposal_base_keeps_its_content(self):
		template = self._template("<p>A</p>")
		self._save_template(template, "<p>B</p>")
		base = self._template_versions(template)[-1].name
		candidate = template_at_version(template.name, base)
		candidate.content = "<p>Vorschlag</p>"
		versioning.create_version(TEMPLATE_VERSION_SPEC, candidate, source="KI-Vorschlag", based_on=base, force=True)

		self._save_template(template, "<p>C</p>")

		self.assertIn("<p>B</p>", frappe.db.get_value("Serienbrief Vorlagenversion", base, "snapshot"))

	def test_sealing_refuses_a_version_that_changed_meanwhile(self):
		block = self._block("Parallel", "<p>eins</p>")
		self._edit(block, "<p>zwei</p>")
		latest = self._block_versions(block)[-1]

		self.assertFalse(versioning._seal_if_unchanged(tbv.SPEC, latest.name, "anderer-inhalt"))
		self.assertFalse(frappe.db.get_value("Serienbrief Textbausteinversion", latest.name, "sealed"))

		# Hat sich die Version inzwischen geaendert, entsteht eine neue, festgeschriebene.
		frappe.db.set_value("Serienbrief Textbausteinversion", latest.name, "content_hash", "anders")
		name = versioning.ensure_current_version(tbv.SPEC, frappe.get_doc("Serienbrief Textbaustein", block.name), seal=True)
		self.assertNotEqual(name, latest.name)
		self.assertTrue(frappe.db.get_value("Serienbrief Textbausteinversion", name, "sealed"))
