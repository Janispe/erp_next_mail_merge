from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, strip_html_tags

from mail_merge.mail_merge.utils import versioning
from mail_merge.mail_merge.utils import textbaustein_versions as tbv
from mail_merge.mail_merge.utils.serienbrief_pdf_form import extract_pdf_form_field_names


class SerienbriefTextbaustein(Document):
	def validate(self):
		previous = self.get_doc_before_save()
		if previous and previous.get("assistant_created"):
			self.assistant_created = 1
		if self.get("assistant_created"):
			from mail_merge.mail_merge.utils.assistant_templates import validate_assistant_source

			if self.content_type == "PDF Formular":
				from mail_merge.mail_merge.utils.assistant_assets import validate_pdf_block

				validate_pdf_block(self)
			elif self.content_type == "HTML + Jinja":
				validate_assistant_source(tbv.snapshot_content(self.as_dict()))
			else:
				frappe.throw(_("KI-Textbausteine müssen HTML + Jinja oder PDF Formular verwenden."))
		content_type = cstr(getattr(self, "content_type", None) or "").strip() or "Textbaustein (Rich Text)"
		self.content_type = content_type
		if content_type != "PDF Formular":
			return

		if not cstr(getattr(self, "pdf_file", None) or "").strip():
			frappe.throw(_("Bitte eine PDF-Datei auswählen."))

	def after_insert(self):
		tbv.create_textbaustein_version(self, default_source="Ausgangsstand")

	def on_update(self):
		tbv.create_textbaustein_version(self)

	def after_rename(self, old: str, new: str, merge: bool = False):
		# ``textbaustein`` ist ein Data-Feld; die Historie zieht bei Umbenennung explizit mit.
		if not merge:
			versioning.rename_versions(tbv.SPEC, old, new)


@frappe.whitelist()
def get_pdf_form_fields(docname: str | None = None, pdf_file: str | None = None) -> list[str]:
	file_url = cstr(pdf_file or "").strip()
	if not file_url and docname:
		doc = frappe.get_doc("Serienbrief Textbaustein", docname)
		file_url = cstr(getattr(doc, "pdf_file", None) or "").strip()
	if not file_url:
		frappe.throw(_("Bitte eine PDF-Datei auswählen."))
	return extract_pdf_form_field_names(file_url)


def _require_access(textbaustein: str | None, ptype: str) -> str:
	name = cstr(textbaustein or "").strip()
	if not name or not frappe.has_permission("Serienbrief Textbaustein", ptype, doc=name):
		frappe.throw(_("Keine Berechtigung für die Versionshistorie dieses Textbausteins."), frappe.PermissionError)
	return name


@frappe.whitelist()
def get_textbaustein_versions(textbaustein: str | None = None) -> dict:
	"""Nummerierte Snapshot-Historie eines Textbausteins, neueste Version zuerst."""
	name = _require_access(textbaustein, "read")
	return versioning.list_versions(
		tbv.SPEC,
		frappe.get_doc("Serienbrief Textbaustein", name),
		evidence_names=tbv.versions_used_in_bills(name),
	)


@frappe.whitelist()
def update_textbaustein_version(
	textbaustein: str | None = None,
	version: str | None = None,
	label: str | None = None,
	is_protected: int | str | bool | None = None,
) -> dict:
	"""Bearbeitet nur Bezeichnung und Schutzstatus; der Snapshot bleibt unveränderlich."""
	name = _require_access(textbaustein, "write")
	doc = versioning.require_version(tbv.SPEC, cstr(version or "").strip(), name)
	versioning.update_version_metadata(doc, label=label, is_protected=is_protected)
	items = get_textbaustein_versions(name).get("items") or []
	return next((item for item in items if item.get("name") == doc.name), versioning.version_metadata(doc))


@frappe.whitelist()
def delete_textbaustein_version(textbaustein: str | None = None, version: str | None = None) -> dict:
	"""Löscht nur entbehrliche Versionen; genutzte Stände bleiben als Nachweis erhalten."""
	name = _require_access(textbaustein, "write")
	doc = versioning.require_version(tbv.SPEC, cstr(version or "").strip(), name)
	return versioning.delete_version(tbv.SPEC, doc, name, evidence_names=tbv.versions_used_in_bills(name))


@frappe.whitelist()
def compare_textbaustein_version(textbaustein: str | None = None, version: str | None = None) -> dict:
	"""Vergleich einer historischen Version mit dem aktuellen Stand."""
	name = _require_access(textbaustein, "read")
	version_doc = versioning.require_version(tbv.SPEC, cstr(version or "").strip(), name)
	before = versioning.parse_snapshot(tbv.SPEC, version_doc.snapshot)
	after = versioning.build_snapshot(tbv.SPEC, frappe.get_doc("Serienbrief Textbaustein", name))
	current_hash = versioning.snapshot_hash(after)
	return {
		"from": versioning.version_metadata(version_doc, current_hash=current_hash),
		"to": {"label": _("Aktueller Stand"), "content_hash": current_hash},
		"sections": tbv.change_sections(before, after),
		"diff": versioning.word_diff(_plain_text(before), _plain_text(after)),
	}


def _plain_text(snapshot: dict) -> str:
	return strip_html_tags(tbv.snapshot_content(snapshot)).strip()


@frappe.whitelist()
def restore_textbaustein_version(textbaustein: str | None = None, version: str | None = None) -> dict:
	"""Setzt den Baustein auf einen historischen Stand und speichert ihn als neue Version.

	Die Historie bleibt vollständig: der bisherige Stand ist weiterhin eine eigene
	Version, die neue trägt eine Herkunftskante zur wiederhergestellten.
	"""
	name = _require_access(textbaustein, "write")
	version_doc = versioning.require_version(tbv.SPEC, cstr(version or "").strip(), name)
	snapshot = versioning.parse_snapshot(tbv.SPEC, version_doc.snapshot)
	file_url = cstr(snapshot.get("pdf_file") or "").strip()
	if file_url and not frappe.db.exists("File", {"file_url": file_url}):
		frappe.throw(_("Die PDF-Datei dieser Version ist nicht mehr vorhanden: {0}").format(file_url))
	doc = frappe.get_doc("Serienbrief Textbaustein", name)
	versioning.apply_snapshot(tbv.SPEC, doc, snapshot)
	doc.flags.version_source = "Wiederherstellung"
	doc.flags.version_restored_from = version_doc.name
	doc.flags.version_label = _("Wiederhergestellt aus Version {0}").format(cint(version_doc.version_number))
	doc.flags.force_textbaustein_version = True
	doc.save()
	return {"name": doc.name, "restored_from_version": version_doc.name}


@frappe.whitelist()
def get_textbaustein_usage(textbaustein: str | None = None) -> list[dict]:
	"""Vorlagen, auf die eine Änderung dieses Bausteins sofort wirkt."""
	name = _require_access(textbaustein, "read")
	if not frappe.has_permission("Serienbrief Vorlage", "read"):
		frappe.throw(_("Keine Berechtigung, Vorlagen zu lesen."), frappe.PermissionError)
	return tbv.textbaustein_usage(name)
