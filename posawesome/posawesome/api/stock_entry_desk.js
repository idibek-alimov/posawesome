// Copyright (c) 2026, Youssef Restom / defendicon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stock Entry", {
	refresh: function (frm) {
		if (!frm.is_new() && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Print Barcode Labels (58x40)"), function () {
				const docName = encodeURIComponent(frm.doc.name);
				window.open(`/posapp#/barcode?source_type=Stock%20Entry&source_doc=${docName}`, "_blank");
			}, __("Actions"));
		}
	},
});
