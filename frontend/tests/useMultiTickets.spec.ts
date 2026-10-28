import { beforeEach, describe, expect, it, vi } from "vitest";
import "fake-indexeddb/auto";
import { createPinia, setActivePinia } from "pinia";
import { useInvoiceStore } from "../src/posapp/stores/invoiceStore";
import { useCustomersStore } from "../src/posapp/stores/customersStore";
import {
	useMultiTickets,
	createEmptySlot,
	resetMultiTicketsState,
	type TicketSlot,
} from "../src/posapp/composables/pos/invoice/useMultiTickets";

function installLocalStorageMock() {
	const storage = new Map<string, string>();
	const mockStorage = {
		getItem(key: string) {
			return storage.has(key) ? storage.get(key)! : null;
		},
		setItem(key: string, value: string) {
			storage.set(String(key), String(value));
		},
		removeItem(key: string) {
			storage.delete(String(key));
		},
		clear() {
			storage.clear();
		},
		key(index: number) {
			return Array.from(storage.keys())[index] ?? null;
		},
		get length() {
			return storage.size;
		},
	};

	Object.defineProperty(globalThis, "localStorage", {
		value: mockStorage,
		configurable: true,
		writable: true,
	});
}

describe("useMultiTickets Composable", () => {
	let eventBus: { emit: any; on: any; off: any };

	beforeEach(() => {
		installLocalStorageMock();
		resetMultiTicketsState();
		(globalThis as any).frappe = {
			datetime: {
				nowdate: () => "2026-10-28",
			},
		};
		(globalThis as any).__ = (text: string) => text;
		localStorage.clear();
		setActivePinia(createPinia());

		eventBus = {
			emit: vi.fn(),
			on: vi.fn(),
			off: vi.fn(),
		};
	});

	it("creates 5 empty slots initially", () => {
		const { slots, activeSlotIndex, getSlotLabel } = useMultiTickets({
			posProfile: { customer: "Walk-in" },
			eventBus,
		});

		expect(slots.value.length).toBe(5);
		expect(activeSlotIndex.value).toBe(0);
		expect(getSlotLabel(slots.value[0])).toBe("№1 (Пусто)");
		expect(getSlotLabel(slots.value[1])).toBe("№2 (Пусто)");
	});

	it("formats slot labels according to customer and item count", () => {
		const { getSlotLabel } = useMultiTickets();

		const emptySlot: TicketSlot = createEmptySlot(0);
		expect(getSlotLabel(emptySlot)).toBe("№1 (Пусто)");

		const slotWithItems: TicketSlot = {
			...createEmptySlot(1),
			items: [{ item_code: "ITEM-A", qty: 2 }],
			customerName: "Иван",
		};
		expect(getSlotLabel(slotWithItems)).toBe("№2: Иван (1)");

		const slotWithoutCustomer: TicketSlot = {
			...createEmptySlot(2),
			items: [
				{ item_code: "ITEM-A", qty: 1 },
				{ item_code: "ITEM-B", qty: 1 },
			],
			customerName: "",
		};
		expect(getSlotLabel(slotWithoutCustomer)).toBe("№3 (2)");
	});

	it("switches tabs, preserving cart state between slots", () => {
		const invoiceStore = useInvoiceStore();
		const customersStore = useCustomersStore();

		const { slots, activeSlotIndex, switchToSlot, syncActiveSlotFromStore } =
			useMultiTickets({
				posProfile: { customer: "DefaultCustomer" },
				eventBus,
			});

		// 1. Add item to slot 0 (active)
		invoiceStore.addItem({
			item_code: "SHIRT-1",
			rate: 100,
			qty: 1,
			posa_row_id: "row_1",
		});
		customersStore.setSelectedCustomer("Customer1");
		syncActiveSlotFromStore();

		expect(slots.value[0].items.length).toBe(1);
		expect(slots.value[0].customer).toBe("Customer1");

		// 2. Switch to slot 1
		switchToSlot(1);
		expect(activeSlotIndex.value).toBe(1);
		expect(invoiceStore.items.length).toBe(0); // Slot 1 should be empty

		// 3. Add item to slot 1
		invoiceStore.addItem({
			item_code: "BELT-1",
			rate: 50,
			qty: 2,
			posa_row_id: "row_2",
		});
		customersStore.setSelectedCustomer("Customer2");
		syncActiveSlotFromStore();

		expect(slots.value[1].items.length).toBe(1);

		// 4. Switch back to slot 0
		switchToSlot(0);
		expect(activeSlotIndex.value).toBe(0);
		expect(invoiceStore.items.length).toBe(1);
		expect(invoiceStore.items[0].item_code).toBe("SHIRT-1");
		expect(customersStore.selectedCustomer).toBe("Customer1");
		expect(eventBus.emit).toHaveBeenCalledWith("focus_item_search");

		// 5. Switch back to slot 1
		switchToSlot(1);
		expect(activeSlotIndex.value).toBe(1);
		expect(invoiceStore.items.length).toBe(1);
		expect(invoiceStore.items[0].item_code).toBe("BELT-1");
		expect(customersStore.selectedCustomer).toBe("Customer2");
	});

	it("clears active slot and stays on the active tab", () => {
		const invoiceStore = useInvoiceStore();
		const { slots, activeSlotIndex, clearActiveSlot, syncActiveSlotFromStore, switchToSlot } =
			useMultiTickets({
				posProfile: { customer: "DefaultCustomer" },
				eventBus,
			});

		switchToSlot(2);
		expect(activeSlotIndex.value).toBe(2);

		invoiceStore.addItem({ item_code: "ITEM-X", rate: 20, qty: 1, posa_row_id: "rx" });
		syncActiveSlotFromStore();
		expect(slots.value[2].items.length).toBe(1);

		clearActiveSlot();
		expect(activeSlotIndex.value).toBe(2); // Stays on tab 2
		expect(slots.value[2].items.length).toBe(0);
	});

	it("clears an inactive slot without affecting active slot", () => {
		const invoiceStore = useInvoiceStore();
		const { slots, activeSlotIndex, clearSlot, syncActiveSlotFromStore, switchToSlot } =
			useMultiTickets({
				posProfile: { customer: "DefaultCustomer" },
				eventBus,
			});

		// Slot 0 has items
		switchToSlot(0);
		invoiceStore.addItem({ item_code: "ITEM-0", rate: 10, qty: 1, posa_row_id: "r0" });
		syncActiveSlotFromStore();

		// Slot 1 has items
		switchToSlot(1);
		invoiceStore.addItem({ item_code: "ITEM-1", rate: 20, qty: 1, posa_row_id: "r1" });
		syncActiveSlotFromStore();

		// While on slot 1, clear slot 0
		clearSlot(0);

		expect(activeSlotIndex.value).toBe(1);
		expect(slots.value[0].items.length).toBe(0);
		expect(slots.value[1].items.length).toBe(1);
	});
});
