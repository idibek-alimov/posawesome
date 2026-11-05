import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const fiscalState = vi.hoisted(() => ({ printZReport: vi.fn(async () => true) }));
vi.mock("../src/posapp/composables/pos/payments/useFiscalPrinter", () => ({
    useFiscalPrinter: () => ({ printZReport: fiscalState.printZReport }),
}));

const offlineState = vi.hoisted(() => ({
	openingStorage: null as any,
	queued: 0,
	offline: false,
	clearOpeningStorage: vi.fn(() => {
		offlineState.openingStorage = null;
	}),
}));

vi.mock("../src/offline/index", () => ({
	initPromise: Promise.resolve(),
	startupInitPromise: Promise.resolve(),
	checkDbHealth: vi.fn(),
	getOpeningStorage: vi.fn(() => offlineState.openingStorage),
	setOpeningStorage: vi.fn((value) => {
		offlineState.openingStorage = value;
	}),
	clearOpeningStorage: offlineState.clearOpeningStorage,
	setTaxTemplate: vi.fn(),
	isOffline: vi.fn(() => offlineState.offline),
	getQueuedPayloadCount: vi.fn(() => offlineState.queued),
	getBootstrapSnapshot: vi.fn(() => null),
	setBootstrapSnapshot: vi.fn(),
}));

vi.mock("../src/offline/bootstrapSnapshot", () => ({
	createBootstrapSnapshotFromRegisterData: vi.fn(() => ({})),
}));

import {
	buildSkippedClosingInvoicesPrompt,
	usePosShift,
} from "../src/posapp/composables/pos/shared/usePosShift";
import { useInvoiceStore } from "../src/posapp/stores/invoiceStore";
import { useUIStore } from "../src/posapp/stores/uiStore";

describe("usePosShift closing warnings", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		offlineState.openingStorage = null;
		offlineState.queued = 0;
		offlineState.offline = false;
		offlineState.clearOpeningStorage.mockClear();
        fiscalState.printZReport.mockClear();
		vi.stubGlobal("frappe", {
			session: { user: "test@example.com" },
			datetime: { nowdate: () => "2026-04-28" },
			call: vi.fn(),
			realtime: { emit: vi.fn() },
		});
		vi.spyOn(console, "log").mockImplementation(() => undefined);
		vi.spyOn(console, "info").mockImplementation(() => undefined);
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("includes invoice and cancelled return reference details in the warning prompt", () => {
		vi.stubGlobal("window", {
			__: (value: string) => value,
		});

		const message = buildSkippedClosingInvoicesPrompt([
			{
				invoice: "SINV-RET-0001",
				doctype: "Sales Invoice",
				return_against: "ACC-SINV-2026-00222",
			},
		]);

		expect(message).toContain(
			"1 printed return invoice references a cancelled invoice and will be excluded from closing.",
		);
		expect(message).toContain("SINV-RET-0001");
		expect(message).toContain("ACC-SINV-2026-00222");
		expect(message).toContain("The skipped invoice will remain a draft.");
		expect(message).toContain("Do you want to proceed?");
	});

	it("uses shared opening shift state when local close-shift state is empty", async () => {
		const uiStore = useUIStore();
		uiStore.posOpeningShift = { name: "POS-OPEN-0002" };
		(globalThis as any).frappe.call = vi.fn(() =>
			Promise.resolve({
				message: {
					name: "POS-CLOSE-0002",
				},
			}),
		);

		const shift = usePosShift();
		await shift.get_closing_data();

		expect((globalThis as any).frappe.call).toHaveBeenCalledWith(
			"posawesome.posawesome.doctype.pos_closing_shift.pos_closing_shift.make_closing_shift_from_opening",
			{ opening_shift: uiStore.posOpeningShift },
		);
	});

	it("clears shared opening shift and invoice state after closing shift submit", async () => {
		const uiStore = useUIStore();
		const invoiceStore = useInvoiceStore();
		uiStore.posOpeningShift = { name: "POS-OPEN-0003" };
		invoiceStore.setAdditionalDiscount(75);
		offlineState.openingStorage = {
			pos_opening_shift: { name: "POS-OPEN-0003" },
		};
		(globalThis as any).frappe.call = vi.fn((method: string) => {
			if (method.includes("submit_closing_shift")) {
				return Promise.resolve({
					message: {
						name: "POS-CLOSE-0003",
					},
				});
			}
			return Promise.resolve({ message: null });
		});

		const shift = usePosShift();
		shift.pos_opening_shift.value = { name: "POS-OPEN-0003" };
		shift.pos_profile.value = { name: "Main POS" };
		await shift.submit_closing_pos({ name: "POS-CLOSE-0003" });
		await Promise.resolve();
		await Promise.resolve();
		await new Promise((resolve) => setTimeout(resolve, 0));

		expect(uiStore.posOpeningShift).toBeNull();
		expect(invoiceStore.additionalDiscount).toBe(0);
		expect(offlineState.clearOpeningStorage).toHaveBeenCalled();
	});
	it("blocks closing while local financial records are queued", async () => {
		offlineState.queued = 1;
		expect(await usePosShift().submit_closing_pos({})).toBe(false);
		expect((globalThis as any).frappe.call).not.toHaveBeenCalled();
	});
	it("preserves the active shift and cart when closing fails", async () => {
		const ui = useUIStore();
		const invoice = useInvoiceStore();
		ui.posOpeningShift = { name: "OPEN-1" };
		invoice.setAdditionalDiscount(25);
		(globalThis as any).frappe.call = vi.fn(() =>
			Promise.reject(new Error("server unavailable")),
		);
		vi.spyOn(console, "error").mockImplementation(() => undefined);
		expect(await usePosShift().submit_closing_pos({ print_z_report: true, transfer_to_safe: true })).toBe(false);
        expect(fiscalState.printZReport).not.toHaveBeenCalled();
		expect(ui.posOpeningShift.name).toBe("OPEN-1");
		expect(invoice.additionalDiscount).toBe(25);
		expect(offlineState.clearOpeningStorage).not.toHaveBeenCalled();
	});
});
