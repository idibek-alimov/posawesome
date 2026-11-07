// Controlled request orchestration. No authenticated site or financial writes.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(
	path.join(
		__dirname,
		"../posawesome/posawesome/page/shift_review/shift_review.js",
	),
	"utf8",
);
function harness() {
	const saved = new Map(),
		calls = [];
	const frappe = {
		pages: { "shift-review": {} },
		session: { user: "manager" },
		utils: { escape_html: (s) => String(s).replaceAll("<", "&lt;") },
		get_route: () => ["shift-review"],
		call: async (options) => {
			calls.push(options);
			return { message: {} };
		},
	};
	const context = vm.createContext({
		frappe,
		__: (s) => s,
		localStorage: {
			getItem: (k) => saved.get(k),
			setItem: (k, v) => saved.set(k, v),
			removeItem: (k) => saved.delete(k),
		},
		crypto: { randomUUID: () => "stable-request" },
		navigator: { onLine: true },
		setTimeout,
		clearTimeout,
		format_currency: (v, c) => `${v} ${c}`,
	});
	vm.runInContext(source + "\nglobalThis.App = ShiftReviewApp", context);
	const app = Object.create(context.App.prototype);
	return { app, frappe, calls, saved, context };
}
test("lost response retains exact intent and version, retry uses one request ID", async () => {
	const h = harness(),
		detail = { review: "Review", version: 3 };
	let fail = true;
	h.frappe.call = async (options) => {
		h.calls.push(options);
		if (fail) throw Error("Connection lost");
		return {
			message: {
				operation: {
					client_request_id: options.args.client_request_id,
					state: "Complete",
				},
			},
		};
	};
	await assert.rejects(
		h.app.execute(
			"Missing expense",
			{ amount: 50, reason: "Taxi" },
			detail,
		),
		/Connection lost/,
	);
	assert.equal(h.app.pending().id, "stable-request");
	await assert.rejects(
		h.app.execute(
			"Missing expense",
			{ amount: 20, reason: "Taxi" },
			detail,
		),
		/earlier review request/,
	);
	assert.equal(h.calls.length, 1);
	fail = false;
	await h.app.execute(
		"Missing expense",
		{ amount: 50, reason: "Taxi" },
		detail,
	);
	assert.equal(
		h.calls[0].args.client_request_id,
		h.calls[1].args.client_request_id,
	);
	assert.equal(h.calls[1].args.expected_version, 3);
	assert.equal(h.app.pending(), null);
});
test("validation rollback permits edited input only after authoritative not_found", async () => {
	const h = harness();
	h.frappe.call = async (options) => {
		h.calls.push(options);
		if (options.method.endsWith(".act"))
			throw { exc_type: "TimestampMismatchError" };
		return { message: { status: "not_found" } };
	};
	await assert.rejects(
		h.app.execute(
			"Link source",
			{ reason: "Investigated" },
			{ review: "R", version: 1 },
		),
	);
	assert.equal(h.app.pending(), null);
	assert.equal(
		h.calls[1].method,
		"posawesome.posawesome.shift_review.service.get_outcome",
	);
});
test("unknown validation outcome and malformed success retain request evidence", async () => {
	const h = harness();
	h.frappe.call = async () => ({ message: { status: "Resolved" } });
	await assert.rejects(
		h.app.execute(
			"Cash adjustment",
			{ amount: 50, reason: "Loss" },
			{ review: "R", version: 1 },
		),
		/not confirmed/,
	);
	assert.ok(h.app.pending());
});
test("storage failure prevents a financial request", async () => {
	const h = harness();
	vm.runInContext(
		'localStorage.setItem=()=>{throw Error("storage denied")}',
		h.context,
	);
	await assert.rejects(
		h.app.execute(
			"Cash adjustment",
			{ reason: "Loss" },
			{ review: "R", version: 1 },
		),
		/storage denied/,
	);
	assert.equal(h.calls.length, 0);
});
test("stale list responses cannot overwrite newer scope", async () => {
	const h = harness();
	let resolveOld;
	h.app.sequence = 0;
	h.app.filters = { status: "unresolved" };
	const node = {
		length: 1,
		attr() {
			return this;
		},
		find() {
			return this;
		},
		text() {
			return this;
		},
	};
	h.app.wrapper = node;
	h.app.render_recovery = () => {};
	const rendered = [];
	h.app.render_list = (data) => rendered.push(data.total);
	h.app.call = () =>
		new Promise((resolve) => {
			resolveOld = resolve;
		});
	const old = h.app.show();
	h.app.call = async () => ({ rows: [], total: 2 });
	await h.app.show();
	resolveOld({ rows: [], total: 1 });
	await old;
	assert.deepEqual(rendered, [2]);
});

test("unreadable saved evidence prevents a new financial request", async () => {
	const h = harness();
	h.saved.set(h.app.pending_key(), "{malformed");
	await assert.rejects(
		h.app.execute(
			"Cash adjustment",
			{ reason: "Loss" },
			{ review: "R", version: 1 },
		),
		/Saved review evidence/,
	);
	assert.equal(h.calls.length, 0);
});
test("offline prevents sending a financial intent", async () => {
	const h = harness();
	vm.runInContext("navigator.onLine=false", h.context);
	await assert.rejects(
		h.app.execute(
			"Cash adjustment",
			{ reason: "Loss" },
			{ review: "R", version: 1 },
		),
		/Offline/,
	);
	assert.equal(h.calls.length, 0);
});
