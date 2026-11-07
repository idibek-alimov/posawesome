// Use the same server draft/expectations as POS; do not calculate a second total here.
frappe.ui.form.on("POS Closing Shift", {
	setup(frm) {
		frm.set_query("pos_opening_shift", () => ({ filters: { status: "Open", docstatus: 1 } }));
	},
	refresh(frm) {
		if (frm.doc.shift_review && (frappe.session?.user === "Administrator" || ["Retail Owner", "Retail Manager", "Accounts Manager"].some(role => (frappe.user_roles || []).includes(role))))
			frm.add_custom_button(__("Shift Review"), () => frappe.set_route("shift-review", frm.doc.shift_review));
		if (frm.__closing_docname !== frm.doc.name) {
			frm.__closing_docname = frm.doc.name;
			frm.__loaded_opening = frm.doc.pos_opening_shift;
		}
		if (frm.doc.docstatus === 0 && frm.doc.pos_opening_shift)
			frm.add_custom_button(__("Refresh totals"), () => load_closing_draft(frm));
	},
	pos_opening_shift(frm) {
		if (frm.doc.pos_opening_shift && frm.doc.docstatus === 0) return load_closing_draft(frm);
	},
});
frappe.ui.form.on("POS Closing Shift Detail", {
	closing_amount(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "difference", flt(row.closing_amount) - flt(row.expected_amount));
		frm.toggle_reqd(
			"discrepancy_reason",
			(frm.doc.payment_reconciliation || []).some((row) => flt(row.difference)),
		);
	},
});
async function load_closing_draft(frm) {
	const shift = frm.doc.pos_opening_shift;
	const sequence = (frm.__closing_request = (frm.__closing_request || 0) + 1);
	frm.disable_save();
	try {
		const response = await frappe.call({
			method: "posawesome.posawesome.doctype.pos_closing_shift.pos_closing_shift.make_closing_shift_from_opening",
			args: { opening_shift: { name: shift } },
		});
		if (sequence !== frm.__closing_request || frm.doc.pos_opening_shift !== shift) return;
		if (!response.message?.closing_shift || !response.message.overview?.reconciliation)
			throw new Error(__("Could not load shift totals. Try again before closing."));
		const counts = new Map(
			frm.__loaded_opening === shift
				? (frm.doc.payment_reconciliation || []).map((row) => [
						row.mode_of_payment,
						row.closing_amount,
					])
				: [],
		);
		const reason = frm.__loaded_opening === shift ? frm.doc.discrepancy_reason : "";
		const draft = response.message.closing_shift;
		for (const field of [
			"company",
			"pos_profile",
			"user",
			"period_start_date",
			"period_end_date",
			"pos_transactions",
			"pos_payments",
			"taxes",
			"grand_total",
			"net_total",
			"total_quantity",
		]) {
			await frm.set_value(field, draft[field]);
			if (sequence !== frm.__closing_request || frm.doc.pos_opening_shift !== shift) return;
		}
		await frm.set_value(
			"payment_reconciliation",
			response.message.overview.reconciliation.map((row) => ({
				mode_of_payment: row.mode_of_payment,
				opening_amount: row.opening_amount,
				expected_amount: row.expected_amount,
				closing_amount: counts.get(row.mode_of_payment) ?? null,
				difference: counts.has(row.mode_of_payment)
					? flt(counts.get(row.mode_of_payment)) - flt(row.expected_amount)
					: 0,
			})),
		);
		if (sequence !== frm.__closing_request || frm.doc.pos_opening_shift !== shift) return;
		await frm.set_value("discrepancy_reason", reason || "");
		if (sequence !== frm.__closing_request || frm.doc.pos_opening_shift !== shift) return;
		frm.__loaded_opening = shift;
		frm.toggle_reqd(
			"discrepancy_reason",
			(frm.doc.payment_reconciliation || []).some((row) => flt(row.difference)),
		);
		frm.enable_save();
	} catch (error) {
		if (sequence !== frm.__closing_request) return;
		frappe.msgprint(
			frappe.utils.escape_html(
				error.message || __("Could not load shift totals. Try again before closing."),
			),
		);
		// Keep counts and the refresh action; stale totals must not become a closing.
	}
}
