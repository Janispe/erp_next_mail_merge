import json

import frappe


def execute():
	"""Schreibt Versionen fest, auf die bereits etwas verweist (vor Einfuehrung von ``sealed``)."""
	from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import TEMPLATE_VERSION_SPEC
	from mail_merge.mail_merge.utils import textbaustein_versions, versioning

	template_versions = set()
	for doctype, field in (
		("Serienbrief Durchlauf", "vorlagenversion"),
		("Serienbrief Dokument", "vorlagenversion"),
		("Serienbrief Vorlagenversion", "based_on"),
		("Serienbrief Vorlagenversion", "restored_from"),
	):
		if frappe.get_meta(doctype).has_field(field):
			template_versions.update(frappe.get_all(doctype, filters={field: ["is", "set"]}, pluck=field))

	block_versions = set(
		frappe.get_all(
			"Serienbrief Textbausteinversion", filters={"restored_from": ["is", "set"]}, pluck="restored_from"
		)
	)
	for doctype in ("Serienbrief Vorlagenversion", "Serienbrief Dokument"):
		for raw in frappe.get_all(doctype, filters={"textbaustein_versionen": ["is", "set"]}, pluck="textbaustein_versionen"):
			block_versions.update(row.get("version") for row in textbaustein_versionen_rows(raw))
	for raw in frappe.get_all("Serienbrief Vorlage", filters={"baustein_versionen": ["is", "set"]}, pluck="baustein_versionen"):
		for name, number in textbaustein_versions.parse_fixed_versions(raw).items():
			version = textbaustein_versions.version_by_number(name, number)
			if version:
				block_versions.add(version.name)

	for name in template_versions:
		versioning.seal_version(TEMPLATE_VERSION_SPEC, name)
	for name in block_versions:
		versioning.seal_version(textbaustein_versions.SPEC, name)


def textbaustein_versionen_rows(raw):
	try:
		data = json.loads(raw) if isinstance(raw, str) else raw
	except ValueError:
		return []
	return [row for row in (data or []) if isinstance(row, dict) and row.get("version")]
