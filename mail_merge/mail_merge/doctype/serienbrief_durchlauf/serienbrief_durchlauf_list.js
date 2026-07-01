frappe.listview_settings["Serienbrief Durchlauf"] = {
	primary_action() {
		mail_merge.serienbrief.open_new_durchlauf_dialog();
	},
	onload(listview) {
		// "Create your first ..." Empty-State-Button greift nicht durch
		// primary_action – daher auch die make_new_doc-Methode überschreiben.
		listview.make_new_doc = () =>
			mail_merge.serienbrief.open_new_durchlauf_dialog();
	},
};
