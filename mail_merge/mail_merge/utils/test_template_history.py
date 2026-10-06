import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from mail_merge.mail_merge.doctype.serienbrief_textbausteinversion import (
	test_serienbrief_textbausteinversion as base_tests,
)
from mail_merge.mail_merge.doctype.serienbrief_vorlage import serienbrief_vorlage as api
from mail_merge.mail_merge.utils import template_history as history
from mail_merge.mail_merge.utils import versioning


class TestTemplateHistory(IntegrationTestCase):
	setUp = base_tests.TestSerienbriefTextbausteinversion.setUp
	_template = base_tests.TestSerienbriefTextbausteinversion._template

	def chain(self):
		self.suffix = frappe.generate_hash(length=6)
		template = self._template("<p>Basis</p>")
		origin = frappe.get_all(history.VERSION, filters={"vorlage": template.name}, pluck="name")[0]
		names = []
		for i in range(3):
			template.content = f"<p>Vorschlag {i}</p>"
			origin = versioning.create_version(
				api.TEMPLATE_VERSION_SPEC, template, source="KI-Vorschlag", based_on=origin, force=True
			)
			names.append(origin)
		return template, names

	def test_group_and_ungroup_are_persistent_metadata_only(self):
		template, names = self.chain()
		rows = {n: frappe.get_doc(history.VERSION, n).as_dict() for n in names}
		result = api.group_editor_versions(template.name, json.dumps(list(reversed(names))))
		self.assertEqual(result["head"], names[-1])
		self.assertEqual(result["members"], names[:-1])
		items = {i["name"]: i for i in api.get_editor_versions(template.name)["items"]}
		self.assertEqual(items[names[-1]]["group_members"], list(reversed(names[:-1])))
		for n in names:
			doc = frappe.get_doc(history.VERSION, n)
			for field in ("snapshot", "content_hash", "based_on", "is_protected", "textbaustein_versionen"):
				self.assertEqual(doc.get(field), rows[n].get(field))
			self.assertFalse(items[n]["can_delete"])
		self.assertEqual(frappe.get_doc(history.TEMPLATE, template.name).content, "<p>Basis</p>")
		api.ungroup_editor_versions(template.name, names[-1])
		self.assertFalse(any(frappe.get_doc(history.VERSION, n).history_group for n in names))

	def test_grouping_rejects_gaps_branches_and_other_templates(self):
		template, names = self.chain()
		_other, other_names = self.chain()
		for selected in ([names[0], names[2]], [names[0], other_names[1]], [names[0], names[0]], names[:1]):
			with self.assertRaises((frappe.ValidationError, frappe.PermissionError)):
				api.group_editor_versions(template.name, selected)
		self.assertFalse(
			frappe.db.exists(history.VERSION, {"vorlage": template.name, "history_group": ["is", "set"]})
		)

	def test_existing_groups_and_live_versions_cannot_be_regrouped(self):
		template, names = self.chain()
		base = frappe.get_all(
			history.VERSION, filters={"vorlage": template.name, "source": "Ausgangsstand"}, pluck="name"
		)[0]
		with self.assertRaises(frappe.ValidationError):
			api.group_editor_versions(template.name, [base, names[0]])
		api.group_editor_versions(template.name, names)
		with self.assertRaises(frappe.ValidationError):
			api.group_editor_versions(template.name, names)

	def test_stale_metadata_save_keeps_group(self):
		template, names = self.chain()
		stale = frappe.get_doc(history.VERSION, names[0])
		api.group_editor_versions(template.name, names)
		stale.version_label = "Neue Bezeichnung"
		stale.save(ignore_permissions=True)
		self.assertEqual(frappe.get_doc(history.VERSION, names[0]).history_group, names[-1])

	def test_direct_delete_preserves_group_head_and_members(self):
		template, names = self.chain()
		api.group_editor_versions(template.name, names)
		for name in (names[0], names[-1]):
			frappe.db.set_value(history.VERSION, name, "is_protected", 0, update_modified=False)
			with self.assertRaises(frappe.ValidationError):
				frappe.delete_doc(history.VERSION, name, ignore_permissions=True)

	def test_write_permission_is_required(self):
		with patch.object(history.frappe, "has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				history.group_versions("Vorlage", ["a", "b"])
			with self.assertRaises(frappe.PermissionError):
				history.ungroup_versions("Vorlage", "b")

	def run_doc(self, template, version=None):
		return frappe.get_doc(
			{
				"doctype": history.RUN,
				"title": f"Lauf {self.suffix}",
				"vorlage": template.name,
				"vorlagenversion": version,
				"kategorie": "Versionstest",
				"status": "Entwurf",
			}
		).insert(ignore_permissions=True)

	def letter(self, template, run, version=None):
		return frappe.get_doc(
			{
				"doctype": history.DOCUMENT,
				"durchlauf": run.name,
				"vorlage": template.name,
				"vorlagenversion": version,
				"title": f"Brief {self.suffix}",
				"status": "Generiert",
				"html": "<p>Brief</p>",
			}
		).insert(ignore_permissions=True)

	def test_usage_counts_group_members_and_keeps_exact_version(self):
		template, names = self.chain()
		run = self.run_doc(template, names[0])
		letter = self.letter(template, run, names[0])
		self.run_doc(template, names[2])
		self.run_doc(template)
		self.letter(template, run)
		api.group_editor_versions(template.name, names)
		usage = api.get_editor_version_usage(template.name, names[2])
		self.assertEqual(usage["counts"], {"documents": 1, "runs": 2})
		self.assertEqual(usage["items"][0]["name"], letter.name)
		self.assertEqual(usage["items"][0]["version_number"], 2)
		exact = api.get_editor_version_usage(template.name, names[2], include_group=0)
		self.assertEqual(exact["counts"], {"documents": 0, "runs": 1})
		all_letters = api.get_editor_version_usage(template.name)
		self.assertEqual(all_letters["counts"], {"documents": 2, "runs": 3})
		self.assertTrue(any(row["version_number"] is None for row in all_letters["items"]))

	def test_usage_pagination_and_links(self):
		template, names = self.chain()
		run = self.run_doc(template, names[0])
		for _i in range(3):
			self.letter(template, run, names[0])
		first = api.get_editor_version_usage(template.name, names[0], limit=2)
		last = api.get_editor_version_usage(template.name, names[0], limit=2, offset=2)
		self.assertEqual(first["total"], 3)
		self.assertTrue(first["has_more"])
		self.assertFalse(last["has_more"])
		self.assertFalse({i["name"] for i in first["items"]} & {i["name"] for i in last["items"]})
		self.assertTrue(first["items"][0]["url"].startswith("/desk/serienbrief-dokument/"))

	def test_usage_does_not_query_unreadable_records(self):
		template, names = self.chain()
		with (
			patch.object(
				history.frappe, "has_permission", side_effect=lambda dt, *a, **kw: dt == history.TEMPLATE
			),
			patch.object(history.frappe, "get_list") as query,
		):
			result = api.get_editor_version_usage(template.name, names[0])
		self.assertFalse(
			any(
				call.args and call.args[0] in (history.DOCUMENT, history.RUN) for call in query.call_args_list
			)
		)
		self.assertEqual(result["counts"], {"documents": 0, "runs": 0})
		self.assertEqual(result["items"], [])

	def test_pdf_requires_a_readable_attached_file(self):
		row = frappe._dict(name="DOC", generated_pdf_file="/private/files/brief.pdf")
		with (
			patch.object(history.frappe.db, "get_value", return_value="FILE"),
			patch.object(history.frappe, "has_permission", return_value=False),
		):
			self.assertIsNone(history._pdf_url(row))
		with (
			patch.object(history.frappe.db, "get_value", return_value="FILE"),
			patch.object(history.frappe, "has_permission", return_value=True),
		):
			self.assertEqual(history._pdf_url(row), row.generated_pdf_file)
		row.generated_pdf_file = "https://example.com/brief.pdf"
		self.assertIsNone(history._pdf_url(row))
