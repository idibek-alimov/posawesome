// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { printMarketReceipt, renderMarketReceipt } from "../src/posapp/services/marketReceipt";
import { ensureFiscalShift } from "../src/posapp/services/fiscalShift";
import { useFiscalPrinter } from "../src/posapp/composables/pos/payments/useFiscalPrinter";
import { fiscalRequest } from "../src/posapp/services/fiscalTransport";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";
import PaymentActionButtons from "../src/posapp/components/pos/payments/PaymentActionButtons.vue";

vi.mock("../src/offline/index", () => ({ isOffline: () => false, updateLocalStock: vi.fn() }));
vi.mock("../src/posapp/services/qzTray", () => ({ printHtmlViaQz: vi.fn() }));
vi.mock("../src/posapp/services/documentPrint", () => ({ confirmDocumentPrintFallback: vi.fn(), shouldUseConfiguredQzDocumentPrinting: () => false }));
vi.mock("../src/posapp/services/fiscalShift", () => ({ ensureFiscalShift: vi.fn().mockResolvedValue({ shiftStatus: true }), readFiscalStatus: vi.fn() }));
vi.mock("../src/posapp/services/fiscalTransport", () => ({ fiscalRequest: vi.fn(), fiscalContext: vi.fn() }));
const call = vi.fn();
const doc = { name: "INV-001", doctype: "Sales Invoice" };
beforeEach(() => {
	vi.clearAllMocks(); localStorage.clear();
	vi.mocked(ensureFiscalShift).mockResolvedValue({ shiftStatus: true });
	vi.stubGlobal("frappe", { call }); vi.stubGlobal("__", (s: string) => s); (window as any).__ = (s: string) => s;
});

describe("MARKET store receipt", () => {
	it("uses the photographed Tajik layout and server totals without deriving a subtotal from tax-inclusive grand total", () => {
		const html = renderMarketReceipt({ ...doc, posting_date: "2026-11-14", posting_time: "10:45:01", currency: "TJS", tax_id: "030039748",
			receipt_totals: { subtotal: "100", discount: "10", total: "102.6" }, total: 100, grand_total: 102.6, paid_amount: 110, change_amount: 7.4,
			payments: [{ type: "Cash", amount: 50 }, { type: "Bank", amount: 60 }],
			taxes: [{ rate: 14, amount: 12.6, description: "VAT", included_in_print_rate: 0 }],
			items: [{ item_code: "A", item_name: "Рубашка", qty: 2.5, rate: 40, amount: 100 }] });
		const body = new DOMParser().parseFromString(html, "text/html");
		expect(body.documentElement.lang).toBe("tg");
		expect(html).toContain('"Courier New"'); expect(html).toContain("1px dashed");
		expect(body.querySelector(".totals")?.textContent).toBe("ҶАМЪ:100,00ТАХФИФ:10,00");
		expect(body.querySelector(".grand")?.textContent).toBe("ҲАМАГӢ:102,60");
		expect(body.querySelector(".payments")?.textContent).toContain("НАҚДӢ:50,00ҒАЙРИНАҚДӢ:60,00");
		expect(body.querySelector(".calculation")?.textContent).toContain("40,00 × 2.500");
		expect(body.body.textContent).toContain("14.11.26 10:45");
		expect(body.body.textContent).not.toContain("ФД"); expect(html).not.toContain("РАСИДИ ФИСКАЛӢ");
	});
	it("prints through Electron without opening a popup or contacting the fiscal API", async () => {
		const desktop = vi.fn().mockResolvedValue({ accepted: true });
		(window as any).electronAPI = { printStoreReceipt: desktop };
		const popup = vi.spyOn(window, "open");
		call.mockResolvedValue({ message: { ...doc, items: [] } });
		try {
			await printMarketReceipt(doc, { posa_qz_printer_name: "TP809" });
			expect(desktop).toHaveBeenCalledWith(expect.objectContaining({ printerName: "TP809", html: expect.stringContaining('lang="tg"') }));
			expect(popup).not.toHaveBeenCalled(); expect(fiscalRequest).not.toHaveBeenCalled();
		} finally { delete (window as any).electronAPI; popup.mockRestore(); }
	});
	it("renders invoice values, escaped customer/item text, totals, barcode and 80mm page", () => {
		const html = renderMarketReceipt({ ...doc, customer_name: "<script>bad</script>", currency: "TJS", items: [{ item_code: "A", item_name: "Shirt", qty: 2, rate: 40, price_list_rate: 50, amount: 80 }], discount_amount: 5, grand_total: 75, paid_amount: 100, change_amount: 25, stored_value_balance: 9 }, "<svg>barcode</svg>");
		expect(html).toContain("size:80mm"); expect(html).toContain("РАСИДИ МОЛӢ"); expect(html).toContain("&lt;script&gt;");
		expect(html).toContain("ҲАМАГӢ:"); expect(html).toContain("75,00"); expect(html).toContain("100,00"); expect(html).toContain("25,00");
		expect(html).toContain("ТАВОЗУНИ МУШТАРӢ:"); expect(html).toContain("<svg>barcode</svg>");
	});
	it("labels a credit return and preserves absolute amounts", () => {
		const html = renderMarketReceipt({ ...doc, is_return: 1, items: [], grand_total: -10, paid_amount: 0 });
		expect(html).toContain("БАРГАРДОНИДАНИ МОЛ"); expect(html).toContain("БАРГАРДОНИДА ШУД:"); expect(html).toContain("10,00"); expect(html).toContain("Ташаккур барои харид!");
	});
});

describe("fiscal attempts", () => {
	it("does not prepare or transmit a receipt when shift preflight fails", async () => {
		call.mockResolvedValue({ message: { cashier: "Моҳира" } });
		vi.mocked(ensureFiscalShift).mockRejectedValueOnce(new Error("shift blocked"));
		const fiscal = useFiscalPrinter();
		expect((await fiscal.printFiscalReceipt(doc)).success).toBe(false);
		expect(fiscal.fiscalAttemptUnknown.value).toBe(false);
		expect(call).toHaveBeenCalledTimes(1); expect(fiscalRequest).not.toHaveBeenCalled();
	});
	it("keeps an unknown sale untouched without opening a shift or preparing another attempt", async () => {
		call.mockResolvedValue({ message: { status: "Неизвестно" } });
		const fiscal = useFiscalPrinter();
		expect((await fiscal.printFiscalReceipt(doc)).success).toBe(false);
		expect(fiscal.fiscalAttemptUnknown.value).toBe(true);
		expect(ensureFiscalShift).not.toHaveBeenCalled(); expect(fiscalRequest).not.toHaveBeenCalled();
	});
	it("persists FD only after printer SUCCESS using the prepared attempt", async () => {
		call.mockImplementation(async (name: string) => ({ message: name.endsWith("prepare_fiscal_receipt") ? { attempt: "a".repeat(32), payload: { receiptSum: 1000 } } : {} }));
		vi.mocked(fiscalRequest).mockResolvedValue({ rc: "SUCCESS", data: { fdNumber: 12, fpd: "123" } });
		expect((await useFiscalPrinter().printFiscalReceipt(doc)).success).toBe(true);
		expect(call).toHaveBeenLastCalledWith(expect.stringContaining("save_fiscal_data"), expect.objectContaining({ attempt: "a".repeat(32), fiscal_data: expect.objectContaining({ rc: "SUCCESS" }) }));
	});
	it("acknowledges a saved result after ERP failure without transmitting again", async () => {
		let failSave = true;
		call.mockImplementation(async (name: string) => { if (name.endsWith("save_fiscal_data") && failSave) throw new Error("ERP disconnected"); return { message: { attempt: "b".repeat(32), payload: {} } }; });
		vi.mocked(fiscalRequest).mockResolvedValue({ rc: "SUCCESS", data: { fdNumber: 13, fpd: "123" } });
		const fiscal = useFiscalPrinter();
		expect((await fiscal.printFiscalReceipt(doc)).success).toBe(false);
		failSave = false; expect((await fiscal.printFiscalReceipt(doc)).success).toBe(true);
		expect(fiscalRequest).toHaveBeenCalledTimes(1);
	});
	it("does not downgrade or mark a timeout as a known rejection", async () => {
		call.mockResolvedValue({ message: { attempt: "c".repeat(32), payload: {} } });
		vi.mocked(fiscalRequest).mockRejectedValue(new Error("timeout"));
		expect((await useFiscalPrinter().printFiscalReceipt(doc)).success).toBe(false);
		expect(call).toHaveBeenCalledTimes(2);
	});
	it("refuses a no-document reset when printer success is already saved locally", async () => {
		localStorage.setItem("posa-fiscal-result:Sales Invoice:INV-001", "saved-result");
		await expect(useFiscalPrinter().confirmNoFiscalDocument(doc)).rejects.toThrow("already recorded locally");
		expect(call).not.toHaveBeenCalled(); expect(fiscalRequest).not.toHaveBeenCalled();
	});
	it("does not transmit a confirmed fiscal document a second time", async () => {
		call.mockResolvedValue({ message: { completed: true, fdNumber: 14 } });
		expect((await useFiscalPrinter().printFiscalReceipt(doc)).success).toBe(true);
		expect(fiscalRequest).not.toHaveBeenCalled();
	});
});

describe("checkout modes", () => {
	it("has three distinct checkout actions and keeps payment-entry screens separate", async () => {
		const Box = defineComponent({ setup(_, { slots }) { return () => h("div", slots.default?.()); } });
		const Button = defineComponent({ emits: ["click"], setup(_, { slots, emit }) { return () => h("button", { onClick: () => emit("click") }, slots.default?.()); } });
		const global = { components: { VCard: Box, VCol: Box, VRow: Box, VIcon: Box, VBtn: Button } };
		const onSubmitFiscal = vi.fn(); const onSubmitAndPrint = vi.fn();
		const wrapper = mount(PaymentActionButtons, { props: { checkoutModes: true, onSubmitFiscal, onSubmitAndPrint }, global });
		expect(wrapper.text()).toContain("Завершить без чека"); expect(wrapper.text()).toContain("Товарный чек"); expect(wrapper.text()).toContain("С фиск. чеком");
		await wrapper.find('[data-testid="payment-submit-fiscal"]').trigger("click");
		expect(onSubmitFiscal).toHaveBeenCalledTimes(1);
		expect(onSubmitAndPrint).not.toHaveBeenCalled();
		wrapper.unmount();
		const payment = mount(PaymentActionButtons, { global }); expect(payment.find('[data-testid="payment-submit-fiscal"]').exists()).toBe(false);
	});
});

describe("compact returns", () => {
	it("recovers a lost refund response with the same durable request identity", async () => {
		const { default: Returns } = await import("../src/posapp/components/pos/flows/Returns.vue");
		const refund = (Returns as any).methods.refund;
		const refundCall = vi.fn().mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValueOnce({ name: "RET-1", doctype: "Sales Invoice", docstatus: 1, update_stock: 0 });
		const vm: any = { busy: false, error: "", pending: null, pendingKey: "test-return", profile: { name: "Till" },
			rows: [{ name: "row-1", item_code: "A", qty: 2, returnQty: 1, selected: true }], scenario: "receipt", source: { name: "INV-1", doctype: "Sales Invoice" },
			mode: "none", refundType: "cash", uiStore: { posOpeningShift: { name: "SHIFT" }, setLastInvoice: vi.fn() }, call: refundCall };
		await refund.call(vm);
		expect(vm.pending).toBeTruthy(); const identity = vm.pending.request_id;
		await refund.call(vm);
		expect(refundCall.mock.calls.map(args => args[1].request_id)).toEqual([identity, identity]);
		expect(vm.completed.name).toBe("RET-1"); expect(localStorage.getItem(vm.pendingKey)).toBeNull();
	});

	it("does not submit quantities above the remaining source quantity", async () => {
		const { default: Returns } = await import("../src/posapp/components/pos/flows/Returns.vue");
		const vm: any = { busy: false, pending: null, rows: [{ selected: true, qty: 1, returnQty: 2 }], scenario: "receipt", call: vi.fn() };
		await (Returns as any).methods.refund.call(vm);
		expect(vm.call).not.toHaveBeenCalled(); expect(vm.error).toContain("количество");
	});
});
