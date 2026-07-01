app_name = "mail_merge"
app_title = "Mail Merge"
app_publisher = "janis"
app_description = "Generic mail merge core for Frappe"
app_email = ""
app_license = "mit"

app_include_js = [
	"/assets/mail_merge/js/serienbrief_vorlagen_browser.js",
	"/assets/mail_merge/js/serienbrief_durchlauf_dialog.js",
]

extend_bootinfo = "mail_merge.mail_merge.utils.placeholder_cache.extend_bootinfo"

jinja = {
	"methods": [
		"mail_merge.mail_merge.utils.footer.render_document_footer_html",
	],
}

after_migrate = [
	"mail_merge.mail_merge.utils.placeholder_cache.bump_cache_version",
	"mail_merge.install.ensure_serienbrief_settings_defaults",
	"mail_merge.install.ensure_serienbrief_print_format_link_field",
	"mail_merge.install.ensure_serienbrief_dokument_print_format",
]

doc_events = {
	"Serienbrief Vorlage": {
		"on_update": "mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage.enqueue_preview_regeneration",
	},
}
