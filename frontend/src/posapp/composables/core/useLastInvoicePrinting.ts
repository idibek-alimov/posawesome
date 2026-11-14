import { useUIStore } from "../../stores/uiStore";
import { printMarketReceipt } from "../../services/marketReceipt";
import { ref } from "vue";
import { usePaymentPrinting } from "../pos/payments/usePaymentPrinting";

export function useLastInvoicePrinting() {
	const uiStore = useUIStore();
	async function printLastInvoice() {
		if (!uiStore.lastInvoiceId || !uiStore.posProfile) return;
		if (uiStore.lastInvoiceDoctype && !["Sales Invoice", "POS Invoice"].includes(uiStore.lastInvoiceDoctype)) {
			const printing = usePaymentPrinting({ invoiceDoc: ref({ name: uiStore.lastInvoiceId }),
				posProfile: ref(uiStore.posProfile), invoiceType: ref(uiStore.lastInvoiceDoctype) });
			await printing.loadPrintPage({ name: uiStore.lastInvoiceId, doctype: uiStore.lastInvoiceDoctype });
			return;
		}
		await printMarketReceipt({ name: uiStore.lastInvoiceId, doctype: uiStore.lastInvoiceDoctype || undefined }, uiStore.posProfile);
	}
	return { printLastInvoice };
}
