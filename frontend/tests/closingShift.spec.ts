import { beforeEach, describe, expect, it, vi } from "vitest";
import { useClosingShift } from "../src/posapp/composables/pos/closing/useClosingShift";
import {
	actualAmount,
	closingDifference,
} from "../src/posapp/composables/pos/closing/closingAmounts";

const snapshot = () => ({
	company_currency: "TJS",
	reconciliation: [
		{
			mode_of_payment: "Cash",
			opening_amount: 500,
			expected_amount: 600,
			net_received: 100,
			taken_out: 0,
		},
	],
});
describe("shift closing", () => {
	beforeEach(() => vi.stubGlobal("frappe", { call: vi.fn() }));
	it("requires finite actual amounts and treats zero as a real count", () => {
		for (const value of [
			"",
			" ",
			undefined,
			null,
			"abc",
			Infinity,
			"12oops",
		])
			expect(actualAmount(value)).toBeNull();
		expect(actualAmount("0")).toBe(0);
		expect(
			closingDifference({ closing_amount: 550, expected_amount: 600 }),
		).toBe(-50);
		expect(
			closingDifference({ closing_amount: "", expected_amount: 600 }),
		).toBeNull();
	});
	it("keeps the dialog open until submission succeeds and prevents duplicate submits", () => {
		const bus = { emit: vi.fn() };
		const state = useClosingShift(bus);
		state.closingDialog.value = true;
		state.dialog_data.value = {
			payment_reconciliation: [
				{ mode_of_payment: "Cash", closing_amount: "" },
			],
		};
		state.fetchOverview("OPEN-1", "TJS", snapshot());
		expect(state.submitDialog()).toBe(false);
		state.dialog_data.value.payment_reconciliation[0].closing_amount = 0;
		expect(state.submitDialog()).toBe(true);
		expect(state.submitDialog()).toBe(false);
		expect(state.closingDialog.value).toBe(true);
		expect(bus.emit).toHaveBeenCalledTimes(1);
		state.closeDialog();
		expect(state.closingDialog.value).toBe(true);
	});
	it("shows loading errors instead of substituting zero totals", async () => {
		(globalThis as any).frappe.call.mockRejectedValue(new Error("offline"));
		const state = useClosingShift({ emit: vi.fn() });
		await state.fetchOverview("OPEN-1", "TJS");
		expect(state.overview.value).toBeNull();
		expect(state.overviewError.value).toBeTruthy();
		expect(state.submitDialog()).toBe(false);
	});
	it("refreshes the entire closing draft while preserving entered counts", async () => {
		const state = useClosingShift({ emit: vi.fn() });
		state.dialog_data.value = {
			payment_reconciliation: [
				{ mode_of_payment: "Cash", closing_amount: 610 },
			],
		};
		(globalThis as any).frappe.call.mockResolvedValue({
			message: {
				overview: snapshot(),
				closing_shift: {
					pos_transactions: [{ sales_invoice: "INV-NEW" }],
				},
			},
		});
		await state.fetchOverview("OPEN-1", "TJS");
		expect(state.dialog_data.value.pos_transactions[0].sales_invoice).toBe(
			"INV-NEW",
		);
		expect(
			state.dialog_data.value.payment_reconciliation[0].closing_amount,
		).toBe(610);
		expect(
			state.dialog_data.value.payment_reconciliation[0].expected_amount,
		).toBe(600);
	});
	it("ignores a response arriving after the dialog closes", async () => {
		let resolve: any;
		(globalThis as any).frappe.call.mockReturnValue(
			new Promise((done) => {
				resolve = done;
			}),
		);
		const state = useClosingShift({ emit: vi.fn() });
		const pending = state.fetchOverview("OPEN-1", "TJS");
		await Promise.resolve();
		state.closeDialog();
		resolve({ message: { overview: snapshot(), closing_shift: {} } });
		await pending;
		expect(state.overview.value).toBeNull();
	});
});
