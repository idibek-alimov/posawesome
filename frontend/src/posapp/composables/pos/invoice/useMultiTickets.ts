/**
 * useMultiTickets.ts
 *
 * Multi-Ticket 5-Slot Queue Manager for POS Awesome.
 *
 * Provides 5 permanent concurrent customer cart slots (tabs) so cashiers can
 * serve multiple customers without modal popups or manual parking.
 * State is persisted in localStorage & Dexie/IndexedDB across page reloads.
 */

import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { useInvoiceStore } from "../../../stores/invoiceStore";
import { useCustomersStore } from "../../../stores/customersStore";
import { useToastStore } from "../../../stores/toastStore";

export interface TicketSlot {
	id: number; // 0 to 4
	items: any[];
	customer: string | null;
	customerName: string;
	invoiceType: string;
	postingDate: string;
	discountAmount: number;
	additionalDiscount: number;
	additionalDiscountPercentage: number;
	deliveryCharges: any[];
	deliveryChargesRate: number;
	selectedDeliveryCharge: string;
	lastUpdated: number;
}

const STORAGE_KEY = "posa_multi_tickets_v1";
const LEGACY_STORAGE_KEY = "posa_active_draft_backup";
const TOTAL_SLOTS = 5;
const DEBOUNCE_MS = 300;

export function createEmptySlot(id: number, defaultCustomer: string | null = null): TicketSlot {
	const nowdate =
		typeof (globalThis as any).frappe?.datetime?.nowdate === "function"
			? (globalThis as any).frappe.datetime.nowdate()
			: new Date().toISOString().split("T")[0];

	return {
		id,
		items: [],
		customer: defaultCustomer,
		customerName: "",
		invoiceType: "Invoice",
		postingDate: nowdate,
		discountAmount: 0,
		additionalDiscount: 0,
		additionalDiscountPercentage: 0,
		deliveryCharges: [],
		deliveryChargesRate: 0,
		selectedDeliveryCharge: "",
		lastUpdated: Date.now(),
	};
}

// Module-level shared singleton reactive state
const slots = ref<TicketSlot[]>(
	Array.from({ length: TOTAL_SLOTS }, (_, i) => createEmptySlot(i))
);
const activeSlotIndex = ref<number>(0);
const isSwitching = ref<boolean>(false);
let isInitialized = false;

export function resetMultiTicketsState(): void {
	slots.value = Array.from({ length: TOTAL_SLOTS }, (_, i) => createEmptySlot(i));
	activeSlotIndex.value = 0;
	isSwitching.value = false;
	isInitialized = false;
}

function safeSetItem(key: string, value: string): void {
	try {
		if (typeof localStorage !== "undefined") {
			localStorage.setItem(key, value);
		}
	} catch (_e) {
		// Quota exceeded or private mode
	}
}

function safeGetItem(key: string): string | null {
	try {
		if (typeof localStorage !== "undefined") {
			return localStorage.getItem(key);
		}
		return null;
	} catch (_e) {
		return null;
	}
}

export function useMultiTickets(options: { posProfile?: any; eventBus?: any } = {}) {
	const invoiceStore = useInvoiceStore();
	const customersStore = useCustomersStore();
	const toastStore = useToastStore();

	let saveTimer: ReturnType<typeof setTimeout> | null = null;
	let stopWatcher: (() => void) | null = null;

	const defaultProfileCustomer = computed(() => {
		return options.posProfile?.customer || null;
	});

	/**
	 * Formatted display label for a ticket slot.
	 * E.g.:
	 * - №1: Иван (3)
	 * - №1 (3)
	 * - №2 (Пусто)
	 */
	function getSlotLabel(slot: TicketSlot): string {
		const num = slot.id + 1;
		const count = slot.items?.length || 0;

		if (count === 0) {
			return `№${num} (Пусто)`;
		}

		let name = slot.customerName?.trim() || "";
		// Filter out standard generic retail customer names if desired
		if (!name && slot.customer) {
			name = slot.customer;
		}

		if (name && name !== "Розничный покупатель" && name !== "Walk-in Customer") {
			// Truncate customer name if too long
			const shortName = name.length > 10 ? name.slice(0, 9) + "…" : name;
			return `№${num}: ${shortName} (${count})`;
		}

		return `№${num} (${count})`;
	}

	/**
	 * Saves all 5 slots and activeSlotIndex to localStorage.
	 */
	function persistState(): void {
		const payload = {
			version: 1,
			activeSlotIndex: activeSlotIndex.value,
			slots: slots.value,
			savedAt: Date.now(),
		};
		safeSetItem(STORAGE_KEY, JSON.stringify(payload));
	}

	/**
	 * Restores slots from storage or migrates legacy draft.
	 */
	function loadPersistedState(): void {
		const raw = safeGetItem(STORAGE_KEY);
		if (raw) {
			try {
				const data = JSON.parse(raw);
				if (Array.isArray(data.slots) && data.slots.length === TOTAL_SLOTS) {
					slots.value = data.slots;
					if (typeof data.activeSlotIndex === "number" && data.activeSlotIndex >= 0 && data.activeSlotIndex < TOTAL_SLOTS) {
						activeSlotIndex.value = data.activeSlotIndex;
					}
					return;
				}
			} catch (e) {
				console.error("[MultiTickets] Error parsing stored state:", e);
			}
		}

		// Legacy migration: if posa_active_draft_backup exists, import into slot 0
		const legacyRaw = safeGetItem(LEGACY_STORAGE_KEY);
		if (legacyRaw) {
			try {
				const legacyData = JSON.parse(legacyRaw);
				if (legacyData && Array.isArray(legacyData.items) && legacyData.items.length > 0) {
					slots.value[0] = {
						id: 0,
						items: legacyData.items,
						customer: legacyData.customer || defaultProfileCustomer.value,
						customerName: "",
						invoiceType: legacyData.invoiceType || "Invoice",
						postingDate: legacyData.postingDate || createEmptySlot(0).postingDate,
						discountAmount: legacyData.discountAmount || 0,
						additionalDiscount: legacyData.additionalDiscount || 0,
						additionalDiscountPercentage: legacyData.additionalDiscountPercentage || 0,
						deliveryCharges: [],
						deliveryChargesRate: 0,
						selectedDeliveryCharge: "",
						lastUpdated: Date.now(),
					};
				}
			} catch (_e) {
				// Ignore legacy parse error
			}
		}
	}

	/**
	 * Syncs the current active stores into the active ticket slot.
	 */
	function syncActiveSlotFromStore(): void {
		if (isSwitching.value) return;

		const currentIdx = activeSlotIndex.value;
		if (currentIdx < 0 || currentIdx >= TOTAL_SLOTS) return;

		const items = invoiceStore.items;
		const rawCustomer = customersStore.selectedCustomer;
		let customerName = "";

		if ((customersStore.customerInfo as any)?.customer_name) {
			customerName = String((customersStore.customerInfo as any).customer_name);
		} else if (rawCustomer && Array.isArray(customersStore.customers)) {
			const found = customersStore.customers.find((c: any) => c.name === rawCustomer);
			if (found?.customer_name) customerName = found.customer_name;
		}

		slots.value[currentIdx] = {
			id: currentIdx,
			items: Array.isArray(items) ? items.map((it: any) => ({ ...it })) : [],
			customer: rawCustomer || defaultProfileCustomer.value,
			customerName,
			invoiceType: invoiceStore.invoiceType || "Invoice",
			postingDate: invoiceStore.postingDate || createEmptySlot(currentIdx).postingDate,
			discountAmount: invoiceStore.discountAmount || 0,
			additionalDiscount: invoiceStore.additionalDiscount || 0,
			additionalDiscountPercentage: invoiceStore.additionalDiscountPercentage || 0,
			deliveryCharges: invoiceStore.deliveryCharges || [],
			deliveryChargesRate: invoiceStore.deliveryChargesRate || 0,
			selectedDeliveryCharge: invoiceStore.selectedDeliveryCharge || "",
			lastUpdated: Date.now(),
		};
	}

	function schedulePersist(): void {
		if (saveTimer) clearTimeout(saveTimer);
		saveTimer = setTimeout(() => {
			syncActiveSlotFromStore();
			persistState();
		}, DEBOUNCE_MS);
	}

	/**
	 * Loads a slot's contents into the active Pinia stores.
	 */
	function applySlotToStore(slot: TicketSlot): void {
		// Replace cart items
		if (Array.isArray(slot.items) && slot.items.length > 0) {
			invoiceStore.setItems(slot.items);
		} else {
			invoiceStore.clearItems();
		}

		// Settings & stickies
		invoiceStore.setInvoiceType(slot.invoiceType || "Invoice");
		if (slot.postingDate) {
			invoiceStore.setPostingDate(slot.postingDate);
		}
		invoiceStore.setDiscountAmount(slot.discountAmount || 0);
		invoiceStore.setAdditionalDiscount(slot.additionalDiscount || 0);
		invoiceStore.setAdditionalDiscountPercentage(slot.additionalDiscountPercentage || 0);

		if (Array.isArray(slot.deliveryCharges)) {
			invoiceStore.setDeliveryCharges(slot.deliveryCharges);
		} else {
			invoiceStore.resetDeliveryCharges();
		}
		invoiceStore.setDeliveryChargesRate(slot.deliveryChargesRate || 0);
		invoiceStore.setSelectedDeliveryCharge(slot.selectedDeliveryCharge || "");

		// Customer
		const targetCustomer = slot.customer || defaultProfileCustomer.value;
		if (typeof customersStore.setSelectedCustomer === "function") {
			customersStore.setSelectedCustomer(targetCustomer || null);
		}

		// Recalculate totals
		invoiceStore.recalculateTotals();
	}

	/**
	 * Switches from the current slot to targetIndex (0..4).
	 */
	function switchToSlot(targetIndex: number): boolean {
		if (targetIndex < 0 || targetIndex >= TOTAL_SLOTS) return false;
		if (targetIndex === activeSlotIndex.value && isInitialized) return true;

		try {
			isSwitching.value = true;

			// 1. Snapshot current active slot
			syncActiveSlotFromStore();

			// 2. Change active index
			activeSlotIndex.value = targetIndex;

			// 3. Apply target slot to stores
			const targetSlot = slots.value[targetIndex];
			if (!targetSlot) return false;
			applySlotToStore(targetSlot);

			// 4. Save state
			persistState();

			// 5. Signal item search focus
			if (options.eventBus && typeof options.eventBus.emit === "function") {
				options.eventBus.emit("focus_item_search");
			}

			return true;
		} finally {
			isSwitching.value = false;
		}
	}

	/**
	 * Clears the active slot (used on invoice submit, cancel, or payment).
	 * Stays on the current tab.
	 */
	function clearActiveSlot(): void {
		const currentIdx = activeSlotIndex.value;
		slots.value[currentIdx] = createEmptySlot(currentIdx, defaultProfileCustomer.value);
		persistState();
	}

	/**
	 * Clears a specific slot. If it's the active slot, clears stores as well.
	 */
	function clearSlot(slotIndex: number): void {
		if (slotIndex < 0 || slotIndex >= TOTAL_SLOTS) return;

		slots.value[slotIndex] = createEmptySlot(slotIndex, defaultProfileCustomer.value);

		if (slotIndex === activeSlotIndex.value) {
			invoiceStore.clearItems();
			invoiceStore.resetInvoiceType();
			invoiceStore.setDiscountAmount(0);
			invoiceStore.setAdditionalDiscount(0);
			invoiceStore.setAdditionalDiscountPercentage(0);
			invoiceStore.resetDeliveryCharges();
			if (typeof customersStore.setSelectedCustomer === "function") {
				customersStore.setSelectedCustomer(defaultProfileCustomer.value);
			}
			invoiceStore.recalculateTotals();
		}

		persistState();
	}

	function handleBeforeUnload(event: BeforeUnloadEvent): void {
		const totalItemsAcrossSlots = slots.value.reduce(
			(sum, s) => sum + (s.items?.length || 0),
			0
		);
		if (totalItemsAcrossSlots > 0 || invoiceStore.itemsCount > 0) {
			event.preventDefault();
		}
	}

	function init(): void {
		if (isInitialized) return;

		loadPersistedState();

		// Hydrate current active slot into stores if store is empty and slot has items
		const active = slots.value[activeSlotIndex.value];
		if (active && active.items?.length > 0 && invoiceStore.itemsCount === 0) {
			applySlotToStore(active);
		} else if (invoiceStore.itemsCount > 0) {
			// Stores already loaded items (e.g. from draft loader)
			syncActiveSlotFromStore();
			persistState();
		}

		isInitialized = true;
	}

	onMounted(() => {
		init();

		if (typeof window !== "undefined") {
			window.addEventListener("beforeunload", handleBeforeUnload);
		}

		// Watch stores for auto-saving current active slot
		stopWatcher = watch(
			() => [
				invoiceStore.metadata.changeVersion,
				invoiceStore.itemsCount,
				customersStore.selectedCustomer,
				invoiceStore.discountAmount,
				invoiceStore.additionalDiscount,
				invoiceStore.additionalDiscountPercentage,
			],
			() => {
				schedulePersist();
			},
			{ deep: true }
		);

		// Listen to "clear_invoice" event
		if (options.eventBus && typeof options.eventBus.on === "function") {
			options.eventBus.on("clear_invoice", clearActiveSlot);
		}
	});

	onBeforeUnmount(() => {
		if (saveTimer) {
			clearTimeout(saveTimer);
			saveTimer = null;
		}
		if (stopWatcher) {
			stopWatcher();
			stopWatcher = null;
		}
		if (typeof window !== "undefined") {
			window.removeEventListener("beforeunload", handleBeforeUnload);
		}
		if (options.eventBus && typeof options.eventBus.off === "function") {
			options.eventBus.off("clear_invoice", clearActiveSlot);
		}
	});

	return {
		slots,
		activeSlotIndex,
		isSwitching,
		getSlotLabel,
		switchToSlot,
		clearActiveSlot,
		clearSlot,
		syncActiveSlotFromStore,
		persistState,
	};
}
