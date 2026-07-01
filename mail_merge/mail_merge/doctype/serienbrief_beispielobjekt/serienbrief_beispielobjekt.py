from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class SerienbriefBeispielobjekt(Document):
	def validate(self):
		seen: set[str] = set()
		for row in self.get("werte") or []:
			path = cstr(getattr(row, "pfad", "") or "").strip()
			if not path:
				frappe.throw(_("Jeder Beispielwert braucht einen Pfad."))
			key = path.lower()
			if key in seen:
				frappe.throw(_("Der Beispielpfad {0} ist doppelt.").format(frappe.bold(path)))
			seen.add(key)

			value_type = cstr(getattr(row, "wert_typ", "") or "").strip() or "Text"
			row.wert_typ = value_type
			if value_type == "JSON":
				raw = cstr(getattr(row, "wert", "") or "").strip()
				if raw:
					try:
						json.loads(raw)
					except Exception:
						frappe.throw(_("Der Beispielwert für {0} ist kein gültiges JSON.").format(frappe.bold(path)))
