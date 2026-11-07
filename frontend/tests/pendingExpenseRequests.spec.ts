// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { hasPendingExpenseRequest } from "../src/posapp/composables/pos/closing/pendingExpenses";

describe("expense result confirmation before closing", () => {
	beforeEach(() => {
		localStorage.clear();
		sessionStorage.clear();
		(globalThis as any).frappe = { session: { user: "cashier" } };
	});
	function save(action: string, args: any, storage = localStorage) {
		storage.setItem(
			`quick-expense:cashier:${action}`,
			JSON.stringify({ id: "original-request", args }),
		);
	}
	it("blocks an unknown own-shift record after reload or from another tab", () => {
		save("record_quick_expense", {
			company: "Test",
			pos_opening_shift: "Shift",
		});
		expect(hasPendingExpenseRequest("Shift", "Test")).toBe(true);
		expect(hasPendingExpenseRequest("DifferentShift", "Test")).toBe(false);
		expect(hasPendingExpenseRequest("Shift", "DifferentCompany")).toBe(
			false,
		);
	});
	it("preserves the old same-tab pending request as a blocker", () => {
		save(
			"record_quick_expense",
			{ pos_opening_shift: "Shift" },
			sessionStorage,
		);
		expect(hasPendingExpenseRequest("Shift")).toBe(true);
	});
	it("blocks unresolved cancellation even if its shift is not locally known", () => {
		save("cancel_quick_expense", { company: "Test", expense_name: "QE" });
		expect(hasPendingExpenseRequest("Shift", "Test")).toBe(true);
	});
	it("does not block on other actors or office-only expense input", () => {
		save("record_quick_expense", { company: "Test" });
		expect(hasPendingExpenseRequest("Shift", "Test")).toBe(false);
		localStorage.setItem(
			"quick-expense:someone:record_quick_expense",
			"{}",
		);
		expect(hasPendingExpenseRequest("Shift", "Test")).toBe(false);
	});
	it("corrupt request evidence fails closed and is not removed", () => {
		localStorage.setItem(
			"quick-expense:cashier:record_quick_expense",
			"invalid",
		);
		expect(hasPendingExpenseRequest("Shift", "Test")).toBe(true);
		expect(localStorage.length).toBe(1);
	});
});
