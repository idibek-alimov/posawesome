const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"),
	vm = require("node:vm"),
	path = require("node:path");
function setup() {
	const handlers = {},
		calls = [],
		messages = [],
		updates = [];
	const frappe = {
		ui: { form: { on: (dt, h) => (handlers[dt] = h) } },
		call: async (a) => {
			calls.push(a);
			return {
				message: {
					closing_shift: {
						company: "Test",
						pos_profile: "Register",
						user: "Cashier",
						pos_transactions: [{ sales_invoice: "NEW" }],
					},
					overview: {
						reconciliation: [
							{
								mode_of_payment: "Cash",
								opening_amount: 500,
								expected_amount: 1000,
							},
						],
					},
				},
			};
		},
		utils: { escape_html: (s) => s },
		msgprint: (m) => messages.push(m),
		model: { set_value: (...args) => updates.push(args) },
	};
	const context = vm.createContext({
		frappe,
		locals: {
			Child: { Row: { closing_amount: 950, expected_amount: 1000 } },
		},
		flt: (v) => Number(v || 0),
		__: (s) => s,
	});
	vm.runInContext(
		fs.readFileSync(
			path.resolve(
				__dirname,
				"../posawesome/posawesome/doctype/pos_closing_shift/pos_closing_shift.js",
			),
			"utf8",
		),
		context,
	);
	const frm = {
		doc: {
			name: "CLOSE",
			docstatus: 0,
			pos_opening_shift: "OPEN",
			discrepancy_reason: "Counted twice",
			payment_reconciliation: [
				{ mode_of_payment: "Cash", closing_amount: 950 },
			],
		},
		set_query() {},
		add_custom_button() {},
		async set_value(k, v) {
			this.doc[k] = v;
		},
		disable_save() {
			this.disabled = true;
		},
		enable_save() {
			this.disabled = false;
		},
		toggle_reqd() {},
	};
	return {
		context,
		handlers,
		frappe,
		frm,
		calls,
		messages,
		updates,
		load: () => context.load_closing_draft(frm),
	};
}
test("native form difference follows actual minus expected", () => {
	const h = setup();
	h.handlers["POS Closing Shift Detail"].closing_amount(
		h.frm,
		"Child",
		"Row",
	);
	assert.equal(h.updates[0][3], -50);
});
test("refresh gets the shared server draft and preserves current count and note", async () => {
	const h = setup();
	h.handlers["POS Closing Shift"].refresh(h.frm);
	await h.load();
	assert.match(h.calls[0].method, /make_closing_shift_from_opening$/);
	assert.equal(h.frm.doc.payment_reconciliation[0].expected_amount, 1000);
	assert.equal(h.frm.doc.payment_reconciliation[0].closing_amount, 950);
	assert.equal(h.frm.doc.discrepancy_reason, "Counted twice");
	assert.equal(h.frm.disabled, false);
});
test("selecting another shift clears the previous shift count and explanation", async () => {
	const h = setup();
	h.handlers["POS Closing Shift"].refresh(h.frm);
	h.frm.doc.pos_opening_shift = "OTHER";
	await h.load();
	assert.equal(h.frm.doc.payment_reconciliation[0].closing_amount, null);
	assert.equal(h.frm.doc.discrepancy_reason, "");
});
test("an obsolete draft cannot overwrite a newer shift", async () => {
	const h = setup();
	let resolve;
	h.frappe.call = () => new Promise((done) => (resolve = done));
	const pending = h.load();
	h.frm.doc.pos_opening_shift = "OTHER";
	resolve({
		message: {
			closing_shift: { company: "Wrong" },
			overview: { reconciliation: [] },
		},
	});
	await pending;
	assert.equal(h.frm.doc.company, undefined);
	assert.equal(h.frm.doc.payment_reconciliation[0].closing_amount, 950);
});
test("counts and explanation typed while totals load survive the refresh", async () => {
	const h = setup();
	h.handlers["POS Closing Shift"].refresh(h.frm);
	const response = await h.frappe.call({});
	let resolve;
	h.frappe.call = () => new Promise((done) => (resolve = done));
	const pending = h.load();
	h.frm.doc.payment_reconciliation[0].closing_amount = 970;
	h.frm.doc.discrepancy_reason = "Updated count while refreshing";
	resolve(response);
	await pending;
	assert.equal(h.frm.doc.payment_reconciliation[0].closing_amount, 970);
	assert.equal(
		h.frm.doc.discrepancy_reason,
		"Updated count while refreshing",
	);
});
test("switching shift during native field updates stops the obsolete draft", async () => {
	const h = setup();
	const setValue = h.frm.set_value.bind(h.frm);
	h.frm.set_value = async (field, value) => {
		await setValue(field, value);
		if (field === "company") h.frm.doc.pos_opening_shift = "OTHER";
	};
	await h.load();
	assert.equal(h.frm.doc.pos_profile, undefined);
	assert.equal(h.frm.doc.payment_reconciliation[0].closing_amount, 950);
	assert.equal(h.frm.disabled, true);
});
test("load failure preserves input and leaves submission disabled until a successful refresh", async () => {
	const h = setup();
	h.handlers["POS Closing Shift"].refresh(h.frm);
	h.frappe.call = async () => {
		throw Error("Offline");
	};
	await h.load();
	assert.equal(h.frm.disabled, true);
	assert.equal(h.frm.doc.payment_reconciliation[0].closing_amount, 950);
	assert.equal(h.frm.doc.discrepancy_reason, "Counted twice");
	assert.equal(h.messages[0], "Offline");
});
