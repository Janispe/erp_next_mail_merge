from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from . import recipient_selection, serienbrief_durchlauf as core


class TestRecipientSelection(IntegrationTestCase):
	def setUp(self):
		self.prefix = f"Picker-{frappe.generate_hash(length=8)}"
		category = frappe.get_doc({"doctype": "Serienbrief Kategorie", "title": self.prefix}).insert()
		template = frappe.get_doc({
			"doctype": "Serienbrief Vorlage",
			"title": self.prefix,
			"kategorie": category.name,
			"haupt_verteil_objekt": "Note",
			"content": "<p>Testbrief</p>",
		}).insert()
		self.run = core.create_durchlauf(vorlage=template.name)["docname"]
		for index in range(65):
			frappe.get_doc({
				"doctype": "Note",
				"title": self.label(index),
				"public": 1,
			}).insert()

	def label(self, index):
		return f"{self.prefix} {index:02d}"

	def search(self, **kwargs):
		return core.get_available_recipients(self.run, query=self.prefix, **kwargs)

	def test_pages_sort_and_existing_recipients(self):
		first = self.search()
		second = self.search(offset=25)
		self.assertEqual(first["total"], 65)
		self.assertEqual([item["label"] for item in first["items"]], [self.label(i) for i in range(25)])
		self.assertEqual(second["items"][0]["label"], self.label(25))
		self.assertEqual(self.search(sort="name_desc")["items"][0]["label"], self.label(64))
		selected = [item["id"] for item in first["items"] + second["items"]]
		self.assertEqual(core.add_recipients(self.run, selected), {"added": 50})
		remaining = self.search()
		self.assertEqual(remaining["total"], 15)
		self.assertEqual(remaining["items"][0]["label"], self.label(50))
		self.assertEqual(len(frappe.get_doc("Serienbrief Durchlauf", self.run).iteration_objekte), 50)

	def test_bulk_checks_scope_permissions_and_count_and_does_not_render(self):
		denied = self.search()["items"][0]["id"]
		user_has_permission = frappe.has_permission

		def has_permission(doctype, ptype="read", *args, **kwargs):
			if doctype == "Note" and kwargs.get("doc") == denied:
				return False
			return user_has_permission(doctype, ptype, *args, **kwargs)

		scope = {"label": "Testobjekt"}
		with (
			patch.object(recipient_selection, "_selection_scope", return_value=scope),
			patch.object(frappe, "has_permission", side_effect=has_permission),
			patch.object(core.SerienbriefDurchlauf, "_ensure_dokumente") as render,
		):
			self.assertEqual(self.search()["total"], 64)
			with self.assertRaises(frappe.ValidationError):
				core.add_filtered_recipients(self.run, {"test": "scope"}, 65, self.prefix)
			result = core.add_filtered_recipients(self.run, {"test": "scope"}, 64, self.prefix)
			self.assertEqual(result, {"added": 64, "already_present": 0})
			retry = core.add_filtered_recipients(self.run, {"test": "scope"}, 64, self.prefix)
			self.assertEqual(retry, {"added": 0, "already_present": 64})
			# A small bulk operation must also bypass the draft's automatic render.
			small = core.create_durchlauf(vorlage=frappe.db.get_value("Serienbrief Durchlauf", self.run, "vorlage"))["docname"]
			self.assertEqual(core.add_filtered_recipients(small, {"test": "scope"}, 1, self.label(1))["added"], 1)
			render.assert_not_called()

		stored = frappe.get_doc("Serienbrief Durchlauf", self.run).iteration_objekte
		self.assertEqual(len(stored), 64)
		self.assertNotIn(denied, [row.objekt for row in stored])
