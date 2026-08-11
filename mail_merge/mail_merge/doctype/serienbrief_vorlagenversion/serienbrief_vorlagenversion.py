import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr


class SerienbriefVorlagenversion(Document):
	"""Fester Meilenstein oder kurzfristig zusammengefasster, unbenannter Arbeitsstand."""

	_IMMUTABLE_FIELDS = (
		"vorlage",
		"version_number",
		"source",
		"change_summary",
		"restored_from",
		"content_hash",
		"snapshot",
	)

	def validate(self):
		if self.is_new() or not self.name:
			return
		if self.flags.get("allow_session_refresh"):
			return
		stored = frappe.db.get_value(
			self.doctype,
			self.name,
			self._IMMUTABLE_FIELDS,
			as_dict=True,
		)
		if not stored:
			return
		for fieldname in self._IMMUTABLE_FIELDS:
			if cstr(stored.get(fieldname)) != cstr(self.get(fieldname)):
				frappe.throw(
					_("Der Snapshot einer Vorlagenversion ist unveraenderlich. Nur Bezeichnung und Schutzstatus duerfen geaendert werden."),
					frappe.ValidationError,
				)

	def on_trash(self):
		if cint(self.is_protected):
			frappe.throw(_("Geschuetzte Vorlagenversionen koennen nicht geloescht werden."))
