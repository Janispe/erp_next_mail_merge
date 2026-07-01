import frappe


SERIES_LETTER_PAGES = (
	"serienbrief_browser",
	"serienbrief_editor",
	"serienbrief_durchlauf_viewer",
	"serienbrief_vorlagenbaum",
)


def execute():
	if not frappe.db.exists("Module Def", "Mail Merge"):
		return

	for page_name in SERIES_LETTER_PAGES:
		if frappe.db.exists("Page", page_name):
			frappe.db.set_value("Page", page_name, "module", "Mail Merge", update_modified=False)

	frappe.clear_cache()
