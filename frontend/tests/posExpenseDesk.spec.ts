// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { defineComponent, h } from "vue";
import PosExpenseDesk from "../src/posapp/components/pos/expenses/PosExpenseDesk.vue";
vi.mock("../src/offline/db", () => ({ isOffline: () => false }));
vi.mock("../src/offline/cash_movements", () => ({
	getOfflineCashMovements: () => [],
}));
vi.mock("../src/posapp/format", () => ({
	useFormat: () => ({
		formatCurrency: (v: any, c: string) => `${Number(v).toFixed(2)} ${c}`,
	}),
}));
const context = {
	status: "ready",
	company: "Test",
	pos_profile: "Register",
	pos_opening_shift: "Shift",
	can_record: true,
};
const expense = {
	name: "QE-50",
	amount: 50,
	paid_from: "Till",
	pos_opening_shift: "Shift",
	currency: "TJS",
	docstatus: 1,
};
const data = () => ({
	...context,
	currency: "TJS",
	categories: [{ name: "taxi-id", category_name: "Taxi" }],
	payment_sources: [
		{
			id: "wallet:till",
			label: "Till",
			account: "Till",
			account_type: "Cash",
		},
		{
			id: "wallet:Alif",
			label: "Alif",
			account: "Alif",
			account_type: "Bank",
		},
	],
	employees: [],
	recent_expenses: [],
	summary: { period_total: 100, matching_count: 210 },
	has_more: true,
});
let wrapper: any, api: any, call: any, run: any;
const pending = new Map();
const passthrough = defineComponent({
	setup(_, { slots }) {
		return () => h("div", {}, slots.default?.());
	},
});
async function open() {
	wrapper = mount(PosExpenseDesk, {
		global: {
			plugins: [createPinia()],
			stubs: {
				VBtn: defineComponent({
					setup(_, { slots, attrs }) {
						return () => h("button", attrs, slots.default?.());
					},
				}),
				VForm: defineComponent({
					setup(_, { slots, attrs }) {
						return () => h("form", attrs, slots.default?.());
					},
				}),
				VAlert: passthrough,
				VSelect: true,
				VTextField: true,
				VTextarea: true,
				VFileInput: true,
				VProgressLinear: true,
				VDialog: defineComponent({
					props: ["modelValue"],
					setup(props, { slots }) {
						return () =>
							props.modelValue
								? h("div", {}, slots.default?.())
								: null;
					},
				}),
				VCard: passthrough,
				VCardActions: passthrough,
				VListItem: true,
			},
		},
	});
	await flushPromises();
	return wrapper.vm.$.setupState as any;
}
function valid(vm: any) {
	vm.form.category = "taxi-id";
	vm.form.amount = 50;
}
function deferred() {
	let resolve: (v: any) => void = () => {};
	const promise = new Promise((r) => {
		resolve = r;
	});
	return { promise, resolve };
}
describe("cashier expense workflow", () => {
	beforeEach(() => {
		pending.clear();
		run = vi.fn(async () => ({ expense }));
		api = {
			pending: (action: string) => pending.get(action),
			run,
			check: vi.fn(async (action: string) => {
				pending.delete(action);
				return { ...expense, status: "submitted" };
			}),
		};
		call = vi.fn(async ({ method }: any) => ({
			message: method.endsWith("get_pos_expense_session")
				? context
				: data(),
		}));
		(globalThis as any).frappe = {
			session: { user: "cashier" },
			boot: {},
			require: vi.fn(async () => {}),
			call,
			expense_requests: api,
		};
	});
	afterEach(() => {
		wrapper?.unmount();
		vi.restoreAllMocks();
	});
	it("uses read-only session discovery, an authorized Cash default and the canonical category ID", async () => {
		const vm = await open();
		valid(vm);
		expect(vm.form.source_id).toBe("wallet:till");
		await vm.submitExpense();
		expect(run).toHaveBeenCalledWith(
			"record_quick_expense",
			expect.objectContaining({
				category: "taxi-id",
				amount: 50,
				paid_from: "Till",
				company: "Test",
				pos_opening_shift: "Shift",
			}),
		);
		expect(
			call.mock.calls.some(([r]: any) =>
				r.method.includes("check_opening_shift"),
			),
		).toBe(false);
	});
	it("shows no-shift state without loading a guessed register", async () => {
		call.mockResolvedValue({ message: { status: "no_shift" } });
		const vm = await open();
		expect(vm.session.status).toBe("no_shift");
		expect(call).toHaveBeenCalledTimes(1);
		expect(vm.entryDisabled).toBe(true);
	});
	it("does not guess a wallet without a unique approved Cash source", async () => {
		for (const sources of [
			[{ id: "Alif", account_type: "Bank" }],
			[
				{ id: "a", account_type: "Cash" },
				{ id: "b", account_type: "Cash" },
			],
		]) {
			call.mockImplementation(async ({ method }: any) => ({
				message: method.endsWith("get_pos_expense_session")
					? context
					: { ...data(), payment_sources: sources },
			}));
			const vm = await open();
			expect(vm.form.source_id).toBe("");
			wrapper.unmount();
		}
	});
	it("retains failed input and rejects double submission", async () => {
		const wait = deferred();
		run.mockReturnValue(wait.promise);
		const vm = await open();
		valid(vm);
		vm.form.description = "Taxi receipt";
		const first = vm.submitExpense();
		await vm.submitExpense();
		expect(run).toHaveBeenCalledTimes(1);
		wait.resolve(Promise.reject(new Error("lost response")));
		await first;
		expect(vm.form.amount).toBe(50);
		expect(vm.form.description).toBe("Taxi receipt");
		expect(vm.submitError).toBe("lost response");
	});
	it("checks an old result when current source/category setup is absent", async () => {
		pending.set("record_quick_expense", {
			id: "original-id",
			args: {
				amount: 50,
				paid_from: "Disabled",
				category: "Disabled",
				pos_opening_shift: "Shift",
			},
		});
		call.mockImplementation(async ({ method }: any) => ({
			message: method.endsWith("get_pos_expense_session")
				? context
				: { ...data(), categories: [], payment_sources: [] },
		}));
		const vm = await open();
		expect(vm.isFormValid).toBe(false);
		await vm.checkResult("record_quick_expense");
		expect(api.check).toHaveBeenCalledWith("record_quick_expense");
		expect(run).not.toHaveBeenCalled();
		expect(vm.resultDocument.name).toBe("QE-50");
	});
	it("retries saved intent without requiring current form options", async () => {
		const operation = {
			action: "record_quick_expense",
			id: "original-id",
			args: {
				amount: 50,
				paid_from: "Disabled",
				category: "Disabled",
				pos_opening_shift: "Shift",
			},
		};
		pending.set(operation.action, operation);
		const vm = await open();
		await vm.retryOriginal(operation);
		expect(run).toHaveBeenCalledWith(operation.action, operation.args);
	});
	it("ignores a late response and keeps full totals on Load more", async () => {
		const vm = await open();
		const old = deferred();
		call.mockReturnValueOnce(old.promise).mockResolvedValueOnce({
			message: {
				...data(),
				recent_expenses: [
					{ name: "latest", source_id: "Quick Expense:latest" },
				],
				summary: { period_total: 240, matching_count: 210 },
			},
		});
		const first = vm.applyFilters();
		vm.filters.search = "new";
		await vm.applyFilters();
		old.resolve({ message: { ...data(), summary: { period_total: 999 } } });
		await first;
		expect(vm.summary.period_total).toBe(240);
		call.mockResolvedValueOnce({
			message: {
				...data(),
				recent_expenses: [
					{ name: "page2", source_id: "Quick Expense:page2" },
				],
				summary: { period_total: 240, matching_count: 210 },
			},
		});
		await vm.applyFilters(true);
		expect(vm.recentExpenses).toHaveLength(2);
		expect(vm.summary.period_total).toBe(240);
	});
	it("hides confirmed-looking figures until custom dates are applied", async () => {
		const vm = await open();
		vm.filters.period = "custom";
		vm.filterChanged();
		await flushPromises();
		expect(vm.historyReady).toBe(false);
		expect(wrapper.text()).toContain("Choose dates and apply");
	});
});
