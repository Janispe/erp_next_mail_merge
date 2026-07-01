from __future__ import annotations

from frappe.model.document import Document


class SerienbriefEinstellungen(Document):
	def on_update(self) -> None:
		# Margins are embedded in the static Print Format CSS. Refresh the
		# Print Format when the settings change so new values apply immediately.
		try:
			from mail_merge.install import _ensure_serienbrief_dokument_print_format

			_ensure_serienbrief_dokument_print_format(reason="serienbrief_einstellungen.on_update")
		except Exception:
			# Defensiv: ein Fehler beim Print-Format-Refresh darf den Save der
			# Einstellungen nicht blockieren. Wird beim nächsten Migrate ohnehin nachgezogen.
			import frappe

			try:
				frappe.log_error(
					frappe.get_traceback(),
					"Serienbrief Einstellungen on_update: Print Format Refresh fehlgeschlagen",
				)
			except Exception:
				pass
