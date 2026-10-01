const MM_OFFICE_EXPORT = "mail_merge.mail_merge.utils.office_export.";
let mm_office_export_status = null;

const mm_office_export_enabled = () => {
	if (!mm_office_export_status) {
		mm_office_export_status = frappe
			.xcall(MM_OFFICE_EXPORT + "get_office_export_status")
			.then((r) => !!(r && r.enabled))
			.catch(() => false);
	}
	return mm_office_export_status;
};

const mm_download_office = (dokument, format) => {
	const query = new URLSearchParams({ dokument, format });
	window.open(`/api/method/${MM_OFFICE_EXPORT}download_dokument?${query}`);
};

frappe.ui.form.on("Serienbrief Dokument", {
	async refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.durchlauf) {
			frm.add_custom_button(__("Durchlauf öffnen"), () => {
				frappe.set_route("Form", "Serienbrief Durchlauf", frm.doc.durchlauf);
			});
		}
		const has_letter = frm.doc.html && !["Fehler", "Übersprungen"].includes(frm.doc.status);
		if (has_letter && (await mm_office_export_enabled())) {
			frm.add_custom_button(
				__("Word (.docx)"),
				() => mm_download_office(frm.doc.name, "docx"),
				__("Herunterladen")
			);
			frm.add_custom_button(
				__("LibreOffice (.odt)"),
				() => mm_download_office(frm.doc.name, "odt"),
				__("Herunterladen")
			);
		}
	},
});
