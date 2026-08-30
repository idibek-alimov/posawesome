/**
 * useAutoDraftPersistence
 *
 * Watches the active POS invoice state (cart items, customer, discounts,
 * invoice type, posting date) and debounce-saves it to localStorage under the
 * key `posa_active_draft_backup` whenever anything changes.
 *
 * On mount this will check for a saved backup and, if one exists with cart
 * items, prompt the operator via a toast notification.  The caller is
 * responsible for calling `restoreAutoDraft()` if it decides to restore.
 *
 * `clearAutoDraft()` is called internally whenever the cart is submitted or
 * explicitly cleared; it is also exported so callers can clear after payment.
 *
 * A `beforeunload` event listener warns the browser that there is unsaved
 * data whenever the cart is non-empty, prompting the native "Leave page?" dialog.
 *
 * Designed to be mounted in Pos.vue setup() / onMounted so that it has access
 * to the shared event bus and toast store.
 */

import { watch, onMounted, onBeforeUnmount } from "vue";
import { useInvoiceStore } from "../../../stores/invoiceStore";
import { useCustomersStore } from "../../../stores/customersStore";
import { useToastStore } from "../../../stores/toastStore";

const STORAGE_KEY = "posa_active_draft_backup";
const DEBOUNCE_MS = 400;
const VERSION = 1;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function safeSetItem(key: string, value: string): void {
	try {
		localStorage.setItem(key, value);
	} catch (_e) {
		// Quota exceeded or storage disabled – silently skip.
	}
}

function safeGetItem(key: string): string | null {
	try {
		return localStorage.getItem(key);
	} catch (_e) {
		return null;
	}
}

function safeRemoveItem(key: string): void {
	try {
		localStorage.removeItem(key);
	} catch (_e) {
		// ignore
	}
}

/** Returns the translate helper if globally available, otherwise identity. */
const translate = (text: string): string =>
	typeof (globalThis as any).__ === "function"
		? (globalThis as any).__(text)
		: text;

// ---------------------------------------------------------------------------
// Public composable
// ---------------------------------------------------------------------------

export function useAutoDraftPersistence({
	eventBus,
	enabled = true,
}: {
	eventBus: any;
	enabled?: boolean;
}) {
	if (!enabled || typeof window === "undefined") {
		return {
			clearAutoDraft: () => {},
			restoreAutoDraft: () => false,
			hasSavedAutoDraft: () => false,
		};
	}

	const invoiceStore = useInvoiceStore();
	const customersStore = useCustomersStore();
	const toastStore = useToastStore();

	let saveTimer: ReturnType<typeof setTimeout> | null = null;
	let stopWatcher: (() => void) | null = null;

	// -----------------------------------------------------------------------
	// Persistence helpers
	// -----------------------------------------------------------------------

	function clearAutoDraft(): void {
		safeRemoveItem(STORAGE_KEY);
	}

	function hasSavedAutoDraft(): boolean {
		const raw = safeGetItem(STORAGE_KEY);
		if (!raw) return false;
		try {
			const data = JSON.parse(raw);
			return (
				data &&
				data.v === VERSION &&
				Array.isArray(data.items) &&
				data.items.length > 0
			);
		} catch {
			return false;
		}
	}

	function saveAutoDraft(): void {
		const items = invoiceStore.items;
		if (!Array.isArray(items) || items.length === 0) {
			// Nothing in the cart – remove any stale backup.
			clearAutoDraft();
			return;
		}

		const snapshot = {
			v: VERSION,
			savedAt: Date.now(),
			customer: customersStore.selectedCustomer || null,
			items: items.map((item: any) => ({ ...item })),
			invoiceType: invoiceStore.invoiceType,
			postingDate: invoiceStore.postingDate,
			discountAmount: invoiceStore.discountAmount,
			additionalDiscount: invoiceStore.additionalDiscount,
			additionalDiscountPercentage: invoiceStore.additionalDiscountPercentage,
		};

		safeSetItem(STORAGE_KEY, JSON.stringify(snapshot));
	}

	function scheduleSave(): void {
		if (saveTimer) clearTimeout(saveTimer);
		saveTimer = setTimeout(saveAutoDraft, DEBOUNCE_MS);
	}

	// -----------------------------------------------------------------------
	// Restore
	// -----------------------------------------------------------------------

	function restoreAutoDraft(): boolean {
		const raw = safeGetItem(STORAGE_KEY);
		if (!raw) return false;

		let data: any;
		try {
			data = JSON.parse(raw);
		} catch {
			return false;
		}

		if (!data || data.v !== VERSION) return false;
		if (!Array.isArray(data.items) || !data.items.length) return false;

		// Restore cart state
		invoiceStore.setItems(data.items);

		if (data.invoiceType) {
			invoiceStore.setInvoiceType(data.invoiceType);
		}
		if (data.postingDate) {
			invoiceStore.setPostingDate(data.postingDate);
		}
		if (typeof data.discountAmount === "number") {
			invoiceStore.setDiscountAmount(data.discountAmount);
		}
		if (typeof data.additionalDiscount === "number") {
			invoiceStore.setAdditionalDiscount(data.additionalDiscount);
		}
		if (typeof data.additionalDiscountPercentage === "number") {
			invoiceStore.setAdditionalDiscountPercentage(data.additionalDiscountPercentage);
		}

		// Restore customer directly via the store – no event bus needed.
		if (data.customer) {
			customersStore.setSelectedCustomer(data.customer);
		}

		// Recalculate totals now that items are in place
		invoiceStore.recalculateTotals();

		return true;
	}

	// -----------------------------------------------------------------------
	// Browser beforeunload warning
	// -----------------------------------------------------------------------

	function handleBeforeUnload(event: BeforeUnloadEvent): string | undefined {
		if (invoiceStore.itemsCount > 0) {
			const message = translate(
				"You have unsaved items in your cart. Your cart will be automatically restored on your next visit.",
			);
			event.preventDefault();
			// Modern browsers ignore returnValue but still show the dialog.
			// eslint-disable-next-line no-param-reassign
			event.returnValue = message;
			return message;
		}
		return undefined;
	}

	// -----------------------------------------------------------------------
	// Prompt to restore on mount
	// -----------------------------------------------------------------------

	function promptRestoreIfNeeded(): void {
		if (!hasSavedAutoDraft()) return;

		// Small delay so POS finishes its initialisation first.
		setTimeout(() => {
			const restored = restoreAutoDraft();
			if (restored) {
				toastStore.show({
					title: translate("POS session restored"),
					message: translate(
						"Your previous cart has been automatically restored. Review and continue.",
					),
					color: "info",
				});
			}
		}, 800);
	}

	// -----------------------------------------------------------------------
	// Lifecycle
	// -----------------------------------------------------------------------

	onMounted(() => {
		// Attach the unload guard.
		window.addEventListener("beforeunload", handleBeforeUnload);

		// Watch cart changes and schedule a debounced save.
		stopWatcher = watch(
			() => [
				invoiceStore.metadata.changeVersion,
				invoiceStore.itemsCount,
				customersStore.selectedCustomer,
			],
			() => {
				scheduleSave();
			},
			{ immediate: false },
		);

		// Listen for explicit cart clear events so we can remove the backup.
		if (eventBus && typeof eventBus.on === "function") {
			eventBus.on("clear_invoice", clearAutoDraft);
		}

		// Attempt to restore a saved session.
		promptRestoreIfNeeded();
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
		window.removeEventListener("beforeunload", handleBeforeUnload);

		if (eventBus && typeof eventBus.off === "function") {
			eventBus.off("clear_invoice", clearAutoDraft);
		}
	});

	return {
		clearAutoDraft,
		restoreAutoDraft,
		hasSavedAutoDraft,
	};
}
