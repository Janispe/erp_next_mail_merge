"""Use existing letter/run titles for display without renaming any documents."""

from __future__ import annotations

import frappe


def execute():
	_configure_display("Serienbrief Dokument", "serienbrief_dokument", "title,objekt,durchlauf,vorlage")
	_configure_display("Serienbrief Durchlauf", "serienbrief_durchlauf", "title,vorlage")

	# The generator uses the recipient label, falling back to the linked object.
	# For historical documents without a title, retain that same safe fallback.
	# Avoid document.save(), which could trigger rendering or submitted-doc checks.
	for row in frappe.get_all(
		"Serienbrief Dokument", filters={"title": ["is", "not set"]}, fields=["name", "objekt"]
	):
		if row.objekt:
			frappe.db.set_value("Serienbrief Dokument", row.name, "title", row.objekt, update_modified=False)


def _configure_display(doctype, docname, search_fields):
	frappe.reload_doc("mail_merge", "doctype", docname, force=True)
	properties = {
		"title_field": ("title", "Data"),
		"show_title_field_in_link": ("1", "Check"),
		"search_fields": (search_fields, "Data"),
	}
	# Update only an existing override for these three display properties. Other
	# customizations and the identity of the Property Setter remain unchanged.
	for row in frappe.get_all(
		"Property Setter",
		filters={"doc_type": doctype, "doctype_or_field": "DocType", "property": ["in", list(properties)]},
		fields=["name", "property", "value", "property_type"],
	):
		value, property_type = properties[row.property]
		if str(row.value or "") != value or row.property_type != property_type:
			frappe.db.set_value(
				"Property Setter", row.name, {"value": value, "property_type": property_type}, update_modified=False
			)
	frappe.clear_cache(doctype=doctype)
