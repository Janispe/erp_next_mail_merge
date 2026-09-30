import frappe


def execute():
	"""Legt fuer bestehende Textbausteine einen nachvollziehbaren Ausgangsstand an."""
	if not frappe.db.table_exists("Serienbrief Textbausteinversion"):
		return

	from mail_merge.mail_merge.utils import textbaustein_versions, versioning

	for name in frappe.get_all("Serienbrief Textbaustein", pluck="name"):
		doc = frappe.get_doc("Serienbrief Textbaustein", name)
		versioning.ensure_current_version(textbaustein_versions.SPEC, doc, source="Ausgangsstand")
