from mail_merge.mail_merge.utils.versioning import ImmutableVersionDocument


class SerienbriefVorlagenversion(ImmutableVersionDocument):
	"""Fester Meilenstein oder kurzfristig zusammengefasster, unbenannter Arbeitsstand."""

	_IMMUTABLE_FIELDS = (
		"vorlage",
		"version_number",
		"source",
		"change_summary",
		"restored_from",
		"based_on",
		"assistant_created",
		"content_hash",
		"snapshot",
		"textbaustein_versionen",
	)

	def validate(self):
		# Loaded documents must not overwrite a concurrent presentation change.
		if not self.is_new() and self.meta.has_field("history_group"):
			import frappe

			self.history_group = frappe.db.get_value(
				self.doctype, self.name, "history_group", for_update=True
			)
		super().validate()

	def on_trash(self):
		import frappe

		frappe.db.get_value("Serienbrief Vorlage", self.vorlage, "name", for_update=True)
		super().on_trash()
		group = frappe.db.get_value(self.doctype, self.name, "history_group", for_update=True)
		if group or frappe.db.exists(self.doctype, {"history_group": self.name}):
			frappe.throw("Bitte zuerst die Zusammenfassung dieser Versionshistorie auflösen.")
