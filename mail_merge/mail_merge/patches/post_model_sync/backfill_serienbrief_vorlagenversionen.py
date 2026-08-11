import frappe


def execute():
	"""Legt fuer bestehende Vorlagen einen nachvollziehbaren Ausgangsstand an."""
	if not frappe.db.table_exists("Serienbrief Vorlagenversion"):
		return

	from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import (
		_create_template_version,
	)

	for name in frappe.get_all("Serienbrief Vorlage", pluck="name"):
		doc = frappe.get_doc("Serienbrief Vorlage", name)
		_create_template_version(doc, source="Ausgangsstand")
