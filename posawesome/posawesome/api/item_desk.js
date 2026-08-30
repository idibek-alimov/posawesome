// Copyright (c) 2026, Youssef Restom / defendicon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item", {
	refresh: function (frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Print Labels (58x40)"), function () {
				const itemCode = encodeURIComponent(frm.doc.name);
				window.open(`/posapp#/barcode?item_code=${itemCode}`, "_blank");
			}, __("Actions"));
		}
	},
});
