import json
import os
from io import BytesIO

import frappe
from pypdf import PdfWriter
from frappe.tests import IntegrationTestCase

from mail_merge.mail_merge.doctype.serienbrief_textbaustein import serienbrief_textbaustein as api
from mail_merge.mail_merge.doctype.serienbrief_vorlage import serienbrief_vorlage
from mail_merge.mail_merge.utils import textbaustein_versions as tbv
from mail_merge.mail_merge.utils import versioning
from mail_merge.mail_merge.utils.textbaustein_loader import get_textbaustein, pinned_textbausteine

VERSION = "Serienbrief Textbausteinversion"


def _pdf_bytes(width=10):
	writer = PdfWriter()
	writer.add_blank_page(width=width, height=10)
	out = BytesIO()
	writer.write(out)
	return out.getvalue()


def _versions(name):
	return frappe.get_all(
		VERSION,
		filters={"textbaustein": name},
		fields=["name", "version_number", "source", "restored_from", "change_summary", "snapshot"],
		order_by="version_number asc",
	)


class TestSerienbriefTextbausteinversion(IntegrationTestCase):
	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		if not frappe.db.exists("Serienbrief Kategorie", "Versionstest"):
			frappe.get_doc({"doctype": "Serienbrief Kategorie", "title": "Versionstest"}).insert(
				ignore_permissions=True
			)

	def _block(self, label, text):
		return frappe.get_doc(
			{
				"doctype": "Serienbrief Textbaustein",
				"title": f"{label} {self.suffix}",
				"content_type": "Textbaustein (Rich Text)",
				"text_content": text,
			}
		).insert(ignore_permissions=True)

	def _template(self, content, blocks=()):
		return frappe.get_doc(
			{
				"doctype": "Serienbrief Vorlage",
				"title": f"Vorlage {self.suffix}",
				"kategorie": "Versionstest",
				"content_type": "Textbaustein (Rich Text)",
				"content": content,
				"textbausteine": [{"baustein": block.name} for block in blocks],
			}
		).insert(ignore_permissions=True)

	def _edit(self, block, text, **flags):
		block.reload()
		block.text_content = text
		block.flags.update(flags)
		block.save(ignore_permissions=True)
		return block

	def test_insert_creates_baseline_and_saves_create_versions(self):
		block = self._block("Gruss", "<p>Hallo</p>")
		self._edit(block, "<p>Hallo Welt</p>")
		# Unbenannter Folgespeicher derselben Sitzung wird zusammengefasst.
		self._edit(block, "<p>Hallo liebe Welt</p>")

		rows = _versions(block.name)
		self.assertEqual([row.version_number for row in rows], [1, 2])
		self.assertEqual(rows[0].source, "Ausgangsstand")
		self.assertEqual(rows[1].change_summary, "Inhalt")
		self.assertIn("Hallo liebe Welt", json.loads(rows[1].snapshot)["text_content"])

	def test_unchanged_save_creates_no_version(self):
		block = self._block("Unveraendert", "<p>A</p>")
		block.reload()
		block.save(ignore_permissions=True)
		self.assertEqual(len(_versions(block.name)), 1)

	def test_template_version_records_transitive_block_bill(self):
		inner = self._block("Innen", "<p>Innen</p>")
		outer = self._block("Aussen", f'<p>{{{{ baustein("{inner.name}") }}}}</p>')
		table = self._block("Tabelle", "<p>Tabelle</p>")
		template = self._template(f'<p>{{{{ baustein("{outer.name}") }}}}</p>', blocks=[table])

		version = frappe.get_all(
			"Serienbrief Vorlagenversion",
			filters={"vorlage": template.name},
			fields=["textbaustein_versionen"],
			limit=1,
		)[0]
		bill = {row["baustein"]: row for row in json.loads(version.textbaustein_versionen)}
		self.assertEqual(set(bill), {inner.name, outer.name, table.name})
		self.assertEqual(bill[inner.name]["version"], _versions(inner.name)[-1].name)

	def test_block_change_is_visible_in_template_compare_and_pinned_preview(self):
		block = self._block("Fuss", "<p>Alt</p>")
		template = self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')
		template_version = frappe.get_all(
			"Serienbrief Vorlagenversion",
			filters={"vorlage": template.name},
			fields=["name", "textbaustein_versionen"],
			limit=1,
		)[0]
		self._edit(block, "<p>Neu</p>")

		result = serienbrief_vorlage.compare_editor_version(template.name, template_version.name)
		self.assertIn("Bausteine", result["sections"])
		self.assertEqual([row["baustein"] for row in result["textbaustein_changes"]], [block.name])

		pinned = tbv.pinned_docs_from_bill(template_version.textbaustein_versionen)
		with pinned_textbausteine(pinned):
			self.assertEqual(get_textbaustein(block.name).text_content, "<p>Alt</p>")
		self.assertEqual(get_textbaustein(block.name).text_content, "<p>Neu</p>")

	def test_restore_saves_new_version_with_origin_edge(self):
		block = self._block("Wiederherstellen", "<p>Eins</p>")
		first = _versions(block.name)[0]
		self._edit(block, "<p>Zwei</p>")

		api.restore_textbaustein_version(block.name, first.name)

		block.reload()
		self.assertEqual(block.text_content, "<p>Eins</p>")
		latest = _versions(block.name)[-1]
		self.assertEqual(latest.source, "Wiederherstellung")
		self.assertEqual(latest.restored_from, first.name)

	def test_versions_used_by_template_bill_cannot_be_deleted(self):
		block = self._block("Nachweis", "<p>Eins</p>")
		self._edit(block, "<p>Zwei</p>", force_textbaustein_version=True)
		self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')
		self._edit(block, "<p>Drei</p>", force_textbaustein_version=True)

		used = _versions(block.name)[1]
		items = {item["name"]: item for item in api.get_textbaustein_versions(block.name)["items"]}
		self.assertFalse(items[used.name]["can_delete"])
		self.assertIn("Nachweis", items[used.name]["delete_block_reason"])
		with self.assertRaises(frappe.ValidationError):
			api.delete_textbaustein_version(block.name, used.name)

	def test_usage_lists_direct_and_nested_templates(self):
		inner = self._block("Genutzt", "<p>x</p>")
		outer = self._block("Huelle", f'<p>{{{{ baustein("{inner.name}") }}}}</p>')
		template = self._template(f'<p>{{{{ baustein("{outer.name}") }}}}</p>')

		usage = {row["vorlage"]: row for row in api.get_textbaustein_usage(inner.name)}
		self.assertIn(template.name, usage)
		self.assertFalse(usage[template.name]["direkt"])
		self.assertTrue(
			{row["vorlage"]: row for row in api.get_textbaustein_usage(outer.name)}[template.name]["direkt"]
		)

	def test_render_refs_point_to_current_versions(self):
		block = self._block("Render", "<p>x</p>")
		template = self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')
		# Stand am on_update vorbei geschrieben: der Nachweis muss trotzdem stimmen.
		frappe.db.set_value("Serienbrief Textbaustein", block.name, "text_content", "<p>y</p>")
		frappe.clear_document_cache("Serienbrief Textbaustein", block.name)

		refs = tbv.render_version_refs(template)

		self.assertTrue(refs["vorlagenversion"])
		bill = json.loads(refs["textbaustein_versionen"])
		latest = _versions(block.name)[-1]
		self.assertEqual(bill[0]["version"], latest.name)
		self.assertEqual(latest.source, "Systemänderung")
		self.assertIn("<p>y</p>", latest.snapshot)

	def test_pdf_of_old_version_survives_replacement(self):
		old_file = frappe.get_doc(
			{"doctype": "File", "file_name": f"alt-{self.suffix}.pdf", "content": _pdf_bytes(), "is_private": 1}
		).insert(ignore_permissions=True)
		block = frappe.get_doc(
			{
				"doctype": "Serienbrief Textbaustein",
				"title": f"Formular {self.suffix}",
				"content_type": "PDF Formular",
				"pdf_file": old_file.file_url,
			}
		).insert(ignore_permissions=True)
		first = _versions(block.name)[0]
		self.assertEqual(json.loads(first.snapshot)["pdf_file_hash"], old_file.content_hash)

		new_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"neu-{self.suffix}.pdf",
				"content": _pdf_bytes(width=20),
				"is_private": 1,
			}
		).insert(ignore_permissions=True)
		block.reload()
		block.pdf_file = new_file.file_url
		block.save(ignore_permissions=True)
		self.assertIn("PDF-Formular", _versions(block.name)[-1].change_summary)

		path = old_file.get_full_path()
		frappe.delete_doc("File", old_file.name, ignore_permissions=True, force=True)
		self.assertTrue(os.path.exists(path))
		api.restore_textbaustein_version(block.name, first.name)
		block.reload()
		self.assertEqual(block.pdf_file, old_file.file_url)

	def test_hash_changes_when_pdf_content_changes_under_same_url(self):
		snapshot = {"doctype": "Serienbrief Textbaustein", "pdf_file": "/private/files/x.pdf"}
		self.assertNotEqual(
			versioning.snapshot_hash({**snapshot, "pdf_file_hash": "a"}),
			versioning.snapshot_hash({**snapshot, "pdf_file_hash": "b"}),
		)


class TestFixierteTextbausteinversion(IntegrationTestCase):
	"""Standard ist der aktuelle Stand; eine Vorlage kann einen Baustein bewusst fixieren."""

	# Hilfen teilen, ohne die Tests der Basisklasse ein zweites Mal auszufuehren.
	setUp = TestSerienbriefTextbausteinversion.setUp
	_block = TestSerienbriefTextbausteinversion._block
	_template = TestSerienbriefTextbausteinversion._template
	_edit = TestSerienbriefTextbausteinversion._edit

	def _fixed_template(self, block, version_number, content=None, title="Fixiert"):
		return frappe.get_doc(
			{
				"doctype": "Serienbrief Vorlage",
				"title": f"{title} {self.suffix}",
				"kategorie": "Versionstest",
				"content_type": "Textbaustein (Rich Text)",
				"content": content or f'<p>{{{{ baustein("{block.name}") }}}}</p>',
				"baustein_versionen": json.dumps({block.name: version_number}),
			}
		).insert(ignore_permissions=True)

	def test_fixed_version_renders_old_text_while_others_follow_latest(self):
		block = self._block("Fix", "<p>Eins</p>")
		self._edit(block, "<p>Zwei</p>", force_textbaustein_version=True)
		fixed = self._fixed_template(block, 1)
		floating = self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')

		self.assertEqual(get_textbaustein(block.name, template=fixed).text_content, "<p>Eins</p>")
		self.assertEqual(get_textbaustein(block.name, template=floating).text_content, "<p>Zwei</p>")
		html = serienbrief_vorlage._build_raw_template_html(fixed)
		self.assertIn("Eins", html)
		self.assertNotIn("Zwei", html)

	def test_fixing_applies_only_to_that_block_not_to_nested_ones(self):
		inner = self._block("InnenFix", "<p>innen alt</p>")
		outer = self._block("AussenFix", f'<p>aussen alt {{{{ baustein("{inner.name}") }}}}</p>')
		self._edit(outer, f'<p>aussen neu {{{{ baustein("{inner.name}") }}}}</p>', force_textbaustein_version=True)
		self._edit(inner, "<p>innen neu</p>", force_textbaustein_version=True)
		template = self._fixed_template(outer, 1)

		self.assertIn("aussen alt", get_textbaustein(outer.name, template=template).text_content)
		self.assertEqual(get_textbaustein(inner.name, template=template).text_content, "<p>innen neu</p>")

	def test_nested_block_without_table_row_can_be_fixed(self):
		inner = self._block("NurVerschachtelt", "<p>innen alt</p>")
		outer = self._block("Traeger", f'<p>{{{{ baustein("{inner.name}") }}}}</p>')
		self._edit(inner, "<p>innen neu</p>", force_textbaustein_version=True)
		template = self._template(f'<p>{{{{ baustein("{outer.name}") }}}}</p>')
		self.assertNotIn(inner.name, [row.baustein for row in template.textbausteine])

		serienbrief_vorlage.set_template_textbaustein_version(template.name, inner.name, 1)

		template.reload()
		self.assertEqual(get_textbaustein(inner.name, template=template).text_content, "<p>innen alt</p>")
		bill = {row["baustein"]: row for row in tbv.textbaustein_bill(template)}
		self.assertTrue(bill[inner.name]["fixiert"])
		self.assertFalse(bill[outer.name].get("fixiert"))

	def test_bill_marks_fixed_versions_and_compare_ignores_later_block_edits(self):
		block = self._block("FixBill", "<p>Eins</p>")
		template = self._fixed_template(block, 1)
		self._edit(block, "<p>Zwei</p>", force_textbaustein_version=True)

		bill = tbv.textbaustein_bill(template)
		self.assertEqual(bill[0]["version_number"], 1)
		self.assertTrue(bill[0]["fixiert"])
		self.assertEqual(tbv.bill_changes(bill), [])

	def test_invalid_fixed_versions_are_rejected_on_save(self):
		block = self._block("FixFehler", "<p>Eins</p>")
		with self.assertRaises(frappe.ValidationError):
			self._fixed_template(block, 7)
		with self.assertRaises(frappe.ValidationError):
			self._fixed_template(block, 1, title="KeinJson").update({"baustein_versionen": "[1]"}).save(
				ignore_permissions=True
			)

	def test_fixed_versions_are_normalized_and_part_of_template_history(self):
		block = self._block("FixNorm", "<p>Eins</p>")
		template = self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')
		first = frappe.get_all(
			"Serienbrief Vorlagenversion", filters={"vorlage": template.name}, pluck="snapshot"
		)[0]
		# Bestehende Staende ohne Fixierung behalten ihre Pruefsumme.
		self.assertNotIn("baustein_versionen", json.loads(first))

		template.baustein_versionen = json.dumps({block.name: "1", "Leer": 0})
		template.save(ignore_permissions=True)
		self.assertEqual(json.loads(template.baustein_versionen), {block.name: 1})
		latest = frappe.get_all(
			"Serienbrief Vorlagenversion",
			filters={"vorlage": template.name},
			fields=["change_summary"],
			order_by="version_number desc",
			limit=1,
		)[0]
		self.assertIn("Bausteine", latest.change_summary)

	def test_vanished_fixed_version_fails_loudly_instead_of_falling_back(self):
		block = self._block("FixWeg", "<p>Eins</p>")
		template = self._fixed_template(block, 1)
		template.baustein_versionen = json.dumps({block.name: 99})

		with self.assertRaises(frappe.ValidationError):
			get_textbaustein(block.name, template=template)

	def test_fixed_version_cannot_be_deleted(self):
		block = self._block("FixSchutz", "<p>Eins</p>")
		self._edit(block, "<p>Zwei</p>", force_textbaustein_version=True)
		self._edit(block, "<p>Drei</p>", force_textbaustein_version=True)
		self._fixed_template(block, 2)

		second = _versions(block.name)[1]
		self.assertIn(second.name, tbv.versions_used_in_bills(block.name))
		with self.assertRaises(frappe.ValidationError):
			api.delete_textbaustein_version(block.name, second.name)

	def test_pin_api_reports_outdated_and_rejects_unused_blocks(self):
		block = self._block("FixApi", "<p>Eins</p>")
		self._edit(block, "<p>Zwei</p>", force_textbaustein_version=True)
		template = self._template(f'<p>{{{{ baustein("{block.name}") }}}}</p>')

		items = serienbrief_vorlage.set_template_textbaustein_version(template.name, block.name, 1)
		self.assertEqual(items[0]["fixierte_version"], 1)
		self.assertEqual(items[0]["neueste_version"], 2)
		self.assertTrue(items[0]["veraltet"])

		items = serienbrief_vorlage.set_template_textbaustein_version(template.name, block.name, None)
		self.assertIsNone(items[0]["fixierte_version"])

		other = self._block("NichtVerwendet", "<p>x</p>")
		with self.assertRaises(frappe.ValidationError):
			serienbrief_vorlage.set_template_textbaustein_version(template.name, other.name, 1)

	def test_usage_reports_fixed_templates(self):
		block = self._block("FixNutzung", "<p>Eins</p>")
		template = self._fixed_template(block, 1)
		usage = {row["vorlage"]: row for row in api.get_textbaustein_usage(block.name)}
		self.assertEqual(usage[template.name]["fixierte_version"], 1)
