// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises, config } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { createPinia, setActivePinia } from "pinia";
import PurchaseHistory from "../src/posapp/components/pos/flows/PurchaseHistory.vue";
import ReceiptHistory from "../src/posapp/components/pos/flows/ReceiptHistory.vue";
import InvoiceActionButtons from "../src/posapp/components/pos/invoice/InvoiceActionButtons.vue";
import { bus } from "../src/posapp/bus";
import { useUIStore } from "../src/posapp/stores/uiStore";
import { printMarketReceipt } from "../src/posapp/services/marketReceipt";
import { isOffline, isManualOffline } from "../src/offline/index";

vi.mock("../src/offline/index", () => ({ isOffline: vi.fn(() => false), isManualOffline: vi.fn(() => false), updateLocalStock: vi.fn() }));
vi.mock("../src/posapp/services/marketReceipt", () => ({ printMarketReceipt: vi.fn() }));
const call = vi.fn();
const selected = vi.fn();
const sale = { name: "SI-MORNING", doctype: "Sales Invoice", posting_date: "2026-11-14", posting_time: "08:15:00", customer_name: "Моҳира", customer_phone: "+992900123456", grand_total: 100, currency: "TJS", pos_profile: "Till", sales_person: "Шоҳрух" };
const box = (tag = "div") => defineComponent({ setup(_, { slots }) { return () => h(tag, slots.default?.()); } });
const stubs = {
	VTextField: defineComponent({ props: ["modelValue", "label", "disabled"], emits: ["update:modelValue"], setup(props, { emit }) {
		return () => h("input", { "aria-label": props.label, disabled: props.disabled, value: props.modelValue, onInput: (e: any) => emit("update:modelValue", e.target.value) });
	} }),
	VBtn: box("button"), VCard: box(), VCardTitle: box(), VCardText: box(), VCardActions: box(),
	VDialog: defineComponent({ props: ["modelValue"], setup(props, { slots }) { return () => props.modelValue ? h("div", slots.default?.()) : null; } }),
	VAlert: box(), VTable: box("table"), VSpacer: box(), VProgressLinear: box(),
	VMenu: defineComponent({ setup(_, { slots }) { return () => h("div", [slots.activator?.({ props: {} }), slots.default?.()]); } }),
	VList: box(), VListItem: box(), VListItemTitle: box(),
};
let wrappers: any[] = [];
function history() {
	const wrapper = mount(PurchaseHistory, { props: { profile: { name: "Till" }, actionLabel: "Выбрать", onSelect: selected }, global: { components: stubs } });
	wrappers.push(wrapper); return wrapper;
}
beforeEach(() => {
	vi.clearAllMocks(); vi.mocked(isOffline).mockReturnValue(false); vi.mocked(isManualOffline).mockReturnValue(false);
	setActivePinia(createPinia());
	const translate = (s: string) => s;
	config.global.config.globalProperties = { __: translate };
	vi.stubGlobal("__", translate); (window as any).__ = translate;
	vi.stubGlobal("frappe", { call, datetime: { get_today: () => "2026-11-14" } });
	call.mockResolvedValue({ message: { items: [sale], has_more: false } });
});
afterEach(() => { wrappers.forEach(w => w.unmount()); wrappers = []; bus.all.clear(); vi.useRealTimers(); });

describe("purchase history for returns and ordinary receipts", () => {
	it("loads today's purchases on opening, with time, customer phone, salesperson and amount", async () => {
		const wrapper = history(); await flushPromises();
		expect(call).toHaveBeenCalledWith(expect.stringContaining("purchase_history"), expect.objectContaining({ query: "", from_date: "2026-11-14", to_date: "2026-11-14", start: 0 }));
		expect(wrapper.text()).toContain("14.11.2026 08:15"); expect(wrapper.text()).toContain("Моҳира");
		expect(wrapper.text()).toContain("+992900123456"); expect(wrapper.text()).toContain("Шоҳрух"); expect(wrapper.text()).toContain("100.00 TJS");
		expect(selected).not.toHaveBeenCalled();
	});
	it("uses one search for phone, name or salesperson and permits an older date range without auto-selecting", async () => {
		vi.useFakeTimers(); const wrapper = history(); await flushPromises();
		await wrapper.get('input[aria-label="Телефон, имя, продавец, чек или ФД №"]').setValue("900123456");
		await wrapper.get('input[aria-label="Покупки с"]').setValue("2026-11-01");
		await vi.advanceTimersByTimeAsync(300); await flushPromises();
		expect(call).toHaveBeenLastCalledWith(expect.stringContaining("purchase_history"), expect.objectContaining({ query: "900123456", from_date: "2026-11-01", start: 0 }));
		await wrapper.get('input[aria-label="Телефон, имя, продавец, чек или ФД №"]').setValue("Моҳира");
		await vi.advanceTimersByTimeAsync(300); await flushPromises();
		expect(call.mock.calls.at(-1)?.[1].query).toBe("Моҳира"); expect(selected).not.toHaveBeenCalled();
		expect((wrapper.vm as any).loading).toBe(false);
		await wrapper.get('[data-testid="purchase-action-select"]').trigger("click");
		expect(selected).toHaveBeenCalledWith(sale);
	});
	it("paginates and resets to the first page when search changes", async () => {
		vi.useFakeTimers(); call.mockResolvedValue({ message: { items: [sale], has_more: true } });
		const wrapper = history(); await flushPromises();
		await wrapper.findAll("button").find(b => b.text() === "Далее")!.trigger("click"); await flushPromises();
		expect(call.mock.calls.at(-1)?.[1].start).toBe(20);
		await wrapper.setData({ query: "new" }); await vi.advanceTimersByTimeAsync(300); await flushPromises();
		expect(call.mock.calls.at(-1)?.[1].start).toBe(0);
	});
	it("ignores a stale response arriving while a new search is debouncing", async () => {
		vi.useFakeTimers(); let finish: any;
		call.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
		const wrapper = history(); await wrapper.setData({ query: "new" });
		finish({ message: { items: [{ ...sale, name: "OLD" }], has_more: true } }); await flushPromises();
		expect(wrapper.text()).not.toContain("OLD");
		await vi.advanceTimersByTimeAsync(300); await flushPromises(); expect(wrapper.text()).toContain("SI-MORNING");
	});
	it("shows submitted item details without loading a cart or posting anything", async () => {
		const wrapper = history(); await flushPromises();
		call.mockResolvedValueOnce({ message: { items: [{ item_code: "A", item_name: "Курта", qty: 2, rate: 50, amount: 100 }] } });
		await wrapper.findAll("button").find(b => b.text() === "Товары")!.trigger("click"); await flushPromises();
		expect(call).toHaveBeenLastCalledWith(expect.stringContaining("receipt_data"), { invoice_name: sale.name, doctype: "Sales Invoice" });
		expect(wrapper.text()).toContain("Курта"); expect(selected).not.toHaveBeenCalled();
	});
	it("does not display stale item details after the purchase search changes", async () => {
		vi.useFakeTimers(); const wrapper = history(); await flushPromises(); let finish: any;
		call.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
		const pending = (wrapper.vm as any).toggleDetails(sale);
		await wrapper.setData({ query: "other" });
		finish({ message: { items: [{ item_name: "OLD ITEM" }] } }); await pending;
		await vi.advanceTimersByTimeAsync(300); await flushPromises();
		expect(wrapper.text()).not.toContain("OLD ITEM"); expect((wrapper.vm as any).detailKey).toBe("");
	});
	it("rejects an inverted period before calling the server and explains offline history", async () => {
		const wrapper = history(); await flushPromises(); call.mockClear();
		await wrapper.setData({ fromDate: "2026-11-15" }); await (wrapper.vm as any).refresh();
		expect(call).not.toHaveBeenCalled(); expect(wrapper.text()).toContain("Укажите правильный период");
		vi.mocked(isManualOffline).mockReturnValue(true); await (wrapper.vm as any).refresh(); await flushPromises();
		expect(call).not.toHaveBeenCalled(); expect(wrapper.text()).toContain("требуется соединение");
	});
	it("allows read-only history while an initial or stale server probe still reports offline", async () => {
		vi.mocked(isOffline).mockReturnValue(true);
		const wrapper = history(); await flushPromises();
		expect(call).toHaveBeenCalledTimes(1); expect(wrapper.text()).toContain("SI-MORNING");
	});
	it.each(["classic", "counter-grid"])("opens unified returns & receipts in %s without standalone receipts button", async presentation => {
		const wrapper = mount(InvoiceActionButtons, { props: { pos_profile: { posa_allow_return: 1 }, presentation }, global: { components: stubs } }); wrappers.push(wrapper);
		const open = vi.fn(); bus.on("open_returns", open);
		await wrapper.get('[data-testid="invoice-action-returns"]').trigger("click");
		expect(open).toHaveBeenCalledTimes(1);
		expect(wrapper.text()).toContain("Returns & Receipts");
		expect(wrapper.find('[data-testid="invoice-action-receipts"]').exists()).toBe(false);
	});
	it("prints an earlier selected sale through the ordinary receipt service directly from purchase history", async () => {
		useUIStore().posProfile = { name: "Till" } as any;
		const wrapper = history(); await flushPromises();
		await wrapper.get('[data-testid="purchase-action-print"]').trigger("click"); await flushPromises();
		expect(printMarketReceipt).toHaveBeenCalledWith(sale, expect.objectContaining({ name: "Till" }));
		expect(wrapper.text()).not.toContain("Фискальный чек");
	});
	it("keeps purchase history open on print failure and prevents duplicate in-flight clicks", async () => {
		let reject: any; vi.mocked(printMarketReceipt).mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
		const wrapper = history(); await flushPromises();
		const vm = wrapper.vm as any;
		const pending = vm.printReceipt(sale); await vm.printReceipt(sale);
		expect(printMarketReceipt).toHaveBeenCalledTimes(1);
		reject(new Error("Printer unavailable")); await pending;
		expect(vm.printingSale).toBe(""); expect(vm.error).toBe("Printer unavailable");
	});
	it("loads native remaining return rows only after selecting a purchase", async () => {
		const { default: Returns } = await import("../src/posapp/components/pos/flows/Returns.vue");
		const vm: any = { generation: 0, busy: false, open: true, profile: { name: "Till" },
			call: vi.fn().mockResolvedValue({ name: sale.name, customer: "CUSTOMER", items: [{ name: "ROW", qty: 1, rate: 50 }] }) };
		await (Returns as any).methods.loadSale.call(vm, sale);
		expect(vm.call).toHaveBeenCalledWith("return_items", { invoice_name: sale.name, doctype: "Sales Invoice", pos_profile: "Till" });
		expect(vm.rows).toEqual([expect.objectContaining({ qty: 1, returnQty: 1, selected: false })]);
	});
	it("opens returns with the shared history and retains a separate guest product scan", async () => {
		const { default: Returns } = await import("../src/posapp/components/pos/flows/Returns.vue");
		useUIStore().posProfile = { name: "Till", customer: "Walk-in" } as any;
		localStorage.removeItem("posa-quick-return:Till");
		const wrapper = mount(Returns, { global: { components: stubs, config: { globalProperties: { eventBus: bus } } } }); wrappers.push(wrapper);
		bus.emit("open_returns"); await flushPromises();
		expect(wrapper.findComponent(PurchaseHistory).exists()).toBe(true); expect(wrapper.text()).toContain("SI-MORNING");
		call.mockResolvedValueOnce({ message: { name: sale.name, customer: "CUSTOMER", customer_name: sale.customer_name,
			items: [{ name: "ROW", item_code: "A", item_name: "Курта", qty: 1, rate: 50 }] } });
		await wrapper.get('[data-testid="purchase-action-select"]').trigger("click"); await flushPromises();
		expect((wrapper.vm as any).source.name).toBe(sale.name); expect((wrapper.vm as any).rows[0].selected).toBe(false);
		await wrapper.findAll("button").find(b => b.text() === "Другой чек")!.trigger("click");
		expect(wrapper.findComponent(PurchaseHistory).isVisible()).toBe(true);
		await wrapper.findAll("button").find(b => b.text() === "Возврат без чека")!.trigger("click");
		expect(wrapper.findComponent(PurchaseHistory).exists()).toBe(false);
		expect(wrapper.get('input[aria-label="Штрихкод или код товара"]').exists()).toBe(true);
		expect(call.mock.calls.some(args => /refund|submit|formReceipt/.test(args[0]))).toBe(false);
	});
});
