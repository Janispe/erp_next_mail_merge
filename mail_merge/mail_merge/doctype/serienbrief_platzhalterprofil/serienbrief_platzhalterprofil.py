from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class SerienbriefPlatzhalterprofil(Document):
	def validate(self):
		self.ziel_doctype = (self.ziel_doctype or "").strip()
		if not self.ziel_doctype or not frappe.db.exists("DocType", self.ziel_doctype):
			frappe.throw(_("Bitte einen gültigen Ziel-DocType auswählen."))

		seen: set[str] = set()
		for row in self.get("regeln") or []:
			row.pfadmuster = (row.pfadmuster or "").strip()
			if not row.pfadmuster:
				frappe.throw(_("In Zeile {0} fehlt das Pfadmuster.").format(row.idx))
			key = row.pfadmuster.casefold()
			if key in seen:
				frappe.throw(_("Das Pfadmuster {0} ist mehrfach vorhanden.").format(row.pfadmuster))
			seen.add(key)
