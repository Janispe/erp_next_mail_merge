from types import MethodType
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase
from jinja2 import StrictUndefined

from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import (
	_render_serienbrief_template as render,
)
from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import (
	_render_split_preview_html,
	_render_split_preview_source,
	_split_preview_context,
)
from mail_merge.mail_merge.utils.jinja_readonly import is_read_method, readonly_context, readonly_jenv


class TestJinjaReadonly(IntegrationTestCase):
	"""Vorlagen und Bausteine duerfen beim Rendern nur lesen."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "original"}).insert()

	def _blocked(self, template, **context):
		with self.assertRaises((frappe.ValidationError, frappe.PermissionError), msg=template):
			render(template, {"todo": self.todo.name, **context})

	def test_template_cannot_write_or_delete(self):
		for template in (
			'{{ frappe.db.set_value("ToDo", todo, "description", "x") }}',
			'{{ frappe.delete_doc("ToDo", todo) }}',
			'{{ frappe.rename_doc("ToDo", todo, "neu") }}',
			'{{ frappe.get_doc("ToDo", todo).save() }}',
			'{{ frappe.get_doc("ToDo", todo).delete() }}',
			'{{ frappe.get_doc("ToDo", todo).db_set("description", "x") }}',
			"{{ frappe.db.commit() }}",
			'{{ frappe.db.sql("delete from `tabToDo`") }}',
			"{{ frappe.qb }}",
		):
			self._blocked(template)
		self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "description"), "original")

	def test_context_documents_cannot_be_modified(self):
		doc = frappe.get_doc("ToDo", self.todo.name)
		for template in (
			"{{ objekt.save() }}",
			"{{ objekt.delete() }}",
			'{{ objekt.db_set("status", "Closed") }}',
		):
			self._blocked(template, objekt=doc)
		# Auch ein hineingereichtes frappe-Modul umgeht die Positivliste nicht.
		self._blocked('{{ frappe.delete_doc("ToDo", todo) }}', frappe=frappe)
		self._blocked('{{ database.sql("delete from `tabToDo`") }}', database=frappe.db)
		self.assertTrue(frappe.db.exists("ToDo", self.todo.name))

	def test_no_mail_network_scripts_or_nested_rendering(self):
		for template in (
			'{{ frappe.sendmail(recipients=["a@example.com"], subject="x") }}',
			'{{ frappe.make_post_request("http://example.com") }}',
			"{{ frappe.enqueue }}",
			'{{ frappe.render_template("{{ 1 }}", {}) }}',
			'{{ run_script("x") }}',
			"{{ FrappeClient }}",
			"{{ resolve_class('frappe.model.document.Document') }}",
			"{{ _getattr_(objekt, 'save')() }}",
			"{{ log('x') }}",
			"{{ frappe.log_error('x') }}",
			"{{ frappe.utils.image_to_base64(objekt, 'png') }}",
		):
			self._blocked(template)

	def test_reading_like_existing_templates_still_works(self):
		html = render(
			"{{ frappe.db.get_value('ToDo', todo, 'description') }}|"
			"{{ frappe.get_doc('ToDo', todo).description }}|"
			"{{ frappe.get_cached_doc('ToDo', todo).get('description') }}|"
			"{{ frappe.get_all('ToDo', filters={'name': todo}, pluck='name') | length }}|"
			"{{ frappe.utils.fmt_money(1234.5, currency='EUR') }}|"
			"{{ frappe.utils.formatdate('2030-01-15') }}|"
			"{{ objekt.get_formatted('status') }}",
			{"todo": self.todo.name, "objekt": frappe.get_doc("ToDo", self.todo.name)},
		)
		parts = html.split("|")
		self.assertEqual(parts[:4], ["original", "original", "original", "1"])
		self.assertIn("1", parts[4])
		self.assertTrue(parts[5])
		self.assertEqual(parts[6], "Open")
		with self.assertRaises(frappe.ValidationError):
			render('{{ frappe.throw("Bitte Bankkonto hinterlegen") }}', {})

	def test_blocked_access_explains_itself(self):
		with self.assertRaises(frappe.PermissionError) as ctx:
			render('{{ frappe.delete_doc("ToDo", todo) }}', {"todo": self.todo.name})
		self.assertIn("nur lesen", str(ctx.exception))
		self.assertIn("frappe.delete_doc", str(ctx.exception))

	def test_read_method_rule(self):
		for name in (
			"get",
			"get_formatted",
			"get_kostenmatrix_rows",
			"get_immobilien_basis",
			"as_dict",
			"is_new",
		):
			self.assertTrue(is_read_method(name), name)
		for name in (
			"save",
			"delete",
			"db_set",
			"submit",
			"get_or_create_customer",
			"get_password",
			"get_unreviewed_method",
			"set",
			"run_method",
			"reload",
		):
			self.assertFalse(is_read_method(name), name)

	def test_read_named_controller_method_is_not_implicitly_trusted(self):
		doc = frappe.get_doc("ToDo", self.todo.name)
		calls = []

		def get_unreviewed_method(owner):
			calls.append(owner.name)
			return "unexpected"

		doc.get_unreviewed_method = MethodType(get_unreviewed_method, doc)
		self._blocked("{{ objekt.get_unreviewed_method() }}", objekt=doc)
		self.assertEqual(calls, [])

	def test_custom_hooks_and_filters_are_not_inherited(self):
		from frappe.utils.jinja import get_jenv

		base_env = get_jenv()
		write = Mock(return_value="unexpected")
		with (
			patch.dict(base_env.globals, {"custom_write": write}),
			patch.dict(base_env.filters, {"custom_write": write}),
		):
			self._blocked("{{ custom_write() }}")
			self._blocked("{{ 'x' | custom_write }}")
			# Der normale Frappe-Renderer wird durch das Overlay nicht veraendert.
			self.assertIs(base_env.globals["custom_write"], write)
			self.assertIs(base_env.filters["custom_write"], write)
		write.assert_not_called()

	def test_preview_keeps_read_mocks_and_blocks_writes(self):
		for preview in (_render_split_preview_html, _render_split_preview_source):
			html = preview('{{ frappe.get_doc("Contact", "PREVIEW-0001").name }}')
			self.assertIn("PREVIEW-0001", html)
			for source in (
				'{{ frappe.db.set_value("ToDo", "x", "description", "x") }}',
				'{{ frappe.delete_doc("ToDo", "x") }}',
				'{{ frappe.db.sql("delete from `tabToDo`") }}',
			):
				html = preview(source)
				self.assertIn("hv-preview-error", html)
		self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "description"), "original")
		# Mock-Filter gehen weiter durch den Preview-Proxy, ohne echte DB-Abfrage.
		env = readonly_jenv(undefined=StrictUndefined)
		ctx = readonly_context(env, _split_preview_context())
		with patch.object(frappe.db, "get_all", side_effect=AssertionError("real DB query")):
			self.assertEqual(
				env.from_string(
					'{{ frappe.db.get_all("Contact", filters={"name": objekt}) | length }}'
				).render(ctx),
				"0",
			)

	def test_read_sql_is_used_even_if_parent_environment_has_raw_sql(self):
		from frappe.utils.jinja import get_jenv

		base_db = get_jenv().globals["frappe"]["db"]
		with patch.dict(base_db, {"sql": frappe.db.sql}):
			self._blocked("""{{ frappe.db.sql("delete from `tabToDo`") }}""")
		self.assertTrue(frappe.db.exists("ToDo", self.todo.name))

	def test_local_list_operations_and_jinja_macros_still_work(self):
		self.assertEqual(
			render(
				"{% set ns = namespace(items=[]) %}"
				"{% for value in [3, 1, 2] %}{% set unused = ns.items.append(value) %}{% endfor %}"
				"{% macro label(value) %}{{ value }}{% endmacro %}"
				'{{ label(ns.items | sort | join(",")) }}',
				{},
			),
			"1,2,3",
		)

	def test_body_and_footer_blocks_cannot_delete(self):
		run = frappe.get_doc({"doctype": "Serienbrief Durchlauf"})
		block = frappe.get_doc(
			{
				"doctype": "Serienbrief Textbaustein",
				"name": "Readonly test block",
				"title": "Readonly test block",
				"content_type": "Textbaustein (Rich Text)",
				"text_content": '{{ frappe.delete_doc("ToDo", "' + self.todo.name + '") }}',
			}
		)
		template = frappe.get_doc(
			{
				"doctype": "Serienbrief Vorlage",
				"content_type": "Textbaustein (Rich Text)",
				"content": '{{ baustein("Readonly test block") }}',
			}
		)
		with patch(
			"mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf.get_textbaustein",
			return_value=block,
		):
			with self.assertRaisesRegex(frappe.ValidationError, "nur lesen"):
				run._render_template_content(template, {})
			block.render_position = "Footer"
			with patch.object(run, "_build_footer_context", return_value={}):
				with self.assertRaisesRegex(frappe.ValidationError, "nur lesen"):
					run.render_footer_blocks(template)
		self.assertTrue(frappe.db.exists("ToDo", self.todo.name))
