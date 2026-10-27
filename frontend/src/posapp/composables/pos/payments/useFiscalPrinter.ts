import { ref } from "vue";

declare const frappe: any;
declare const __: (_str: string, _args?: any[]) => string;

export interface FiscalResult {
	success: boolean;
	fdNumber?: string | number;
	fpd?: string;
	shiftNumber?: number;
	receiptNumber?: number;
	onlineStatus?: string;
	error?: string;
	raw?: any;
}

const DEFAULT_BRIDGE_URL = "http://localhost:5000";

export function useFiscalPrinter() {
	const fiscalLoading = ref(false);
	const fiscalError = ref("");
	const fiscalFallbackOpen = ref(false);
	const pendingFiscalInvoice = ref<any>(null);

	const getBridgeUrl = (): string => {
		return DEFAULT_BRIDGE_URL;
	};

	/**
	 * Convert POS invoice doc into TP809 bridge JSON payload
	 */
	const buildFiscalPayload = (invoiceDoc: any) => {
		const items = (invoiceDoc.items || []).map((item: any) => ({
			item_code: item.item_code,
			item_name: item.item_name || item.item_code || "Товар",
			qty: Number(item.qty) || 1,
			rate: Number(item.rate) || 0,
			amount: Number(item.amount) || (Number(item.qty || 1) * Number(item.rate || 0)),
			code: item.custom_marking_code || "",
			is_stock_item: item.is_stock_item !== 0,
		}));

		let cashAmount = 0;
		let cardAmount = 0;

		if (Array.isArray(invoiceDoc.payments) && invoiceDoc.payments.length > 0) {
			invoiceDoc.payments.forEach((p: any) => {
				const mode = (p.mode_of_payment || "").toLowerCase();
				const amt = Number(p.amount) || 0;
				if (mode.includes("card") || mode.includes("карт") || mode.includes("bank") || mode.includes("korti")) {
					cardAmount += amt;
				} else {
					cashAmount += amt;
				}
			});
		} else {
			cashAmount = Number(invoiceDoc.paid_amount || invoiceDoc.grand_total || 0);
		}

		return {
			invoice_name: invoiceDoc.name,
			customer: invoiceDoc.customer || "Клиент",
			customer_email: invoiceDoc.contact_email || invoiceDoc.customer_email || "",
			contact_mobile: invoiceDoc.contact_mobile || "",
			is_return: Boolean(invoiceDoc.is_return),
			items,
			payments: invoiceDoc.payments || [],
			paid_amount_cash: cashAmount,
			paid_amount_card: cardAmount,
			change_amount: Number(invoiceDoc.change_amount) || 0,
			total_taxes_and_charges: Number(invoiceDoc.total_taxes_and_charges) || 0,
			tax_type: "GENERAL",
			vat_code: "STANDARD",
			custom_message: "Ташаккур барои харид! Спасибо за покупку!",
		};
	};

	/**
	 * Send fiscal receipt to TP809 bridge
	 */
	const printFiscalReceipt = async (invoiceDoc: any): Promise<FiscalResult> => {
		fiscalLoading.value = true;
		fiscalError.value = "";
		pendingFiscalInvoice.value = invoiceDoc;

		const payload = buildFiscalPayload(invoiceDoc);
		const bridgeUrl = getBridgeUrl();

		const controller = new AbortController();
		const timeoutId = setTimeout(() => controller.abort(), 12000);

		try {
			const res = await fetch(`${bridgeUrl}/fiscal/print-receipt`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify(payload),
				signal: controller.signal,
			});

			clearTimeout(timeoutId);

			if (!res.ok) {
				const errorData = await res.json().catch(() => ({}));
				const msg = errorData.message || errorData.error || `HTTP error ${res.status}`;
				throw new Error(msg);
			}

			const data = await res.json();
			if (!data.success) {
				throw new Error(data.message || data.error || "Неизвестная ошибка фискализации");
			}

			// Save to backend
			if (typeof frappe !== "undefined" && frappe.call && invoiceDoc.name) {
				await frappe.call("posawesome.posawesome.api.fiscal.save_fiscal_data", {
					invoice_name: invoiceDoc.name,
					doctype: invoiceDoc.doctype || "POS Invoice",
					fiscal_data: data,
				});
			}

			return {
				success: true,
				fdNumber: data.fdNumber,
				fpd: data.fpd,
				shiftNumber: data.shiftNumber,
				receiptNumber: data.receiptNumber,
				onlineStatus: data.onlineStatus,
				raw: data,
			};
		} catch (err: any) {
			clearTimeout(timeoutId);
			const errMsg = err.name === "AbortError" 
				? "Таймаут соединения с фискальным принтером (12 сек)" 
				: (err.message || "Ошибка подключения к принтеру TP809");
			fiscalError.value = errMsg;
			return {
				success: false,
				error: errMsg,
			};
		} finally {
			fiscalLoading.value = false;
		}
	};

	/**
	 * Record invoice as completed without fiscal print (Cashier Fallback)
	 */
	const recordNonFiscal = async (invoiceDoc: any, reason = "Пробито без чека по решению кассира") => {
		if (typeof frappe !== "undefined" && frappe.call && invoiceDoc?.name) {
			await frappe.call("posawesome.posawesome.api.fiscal.record_non_fiscal_sale", {
				invoice_name: invoiceDoc.name,
				doctype: invoiceDoc.doctype || "POS Invoice",
				reason,
			});
		}
	};

	/**
	 * Print Z-Report upon cashier shift closing
	 */
	const printZReport = async (cashierName = "Кассир"): Promise<boolean> => {
		const bridgeUrl = getBridgeUrl();
		try {
			const res = await fetch(`${bridgeUrl}/fiscal/close-shift`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ cashier: cashierName }),
			});
			const data = await res.json().catch(() => ({}));
			return Boolean(data.success);
		} catch (e) {
			console.warn("Failed to print Z-Report on TP809 bridge:", e);
			return false;
		}
	};

	/**
	 * Check printer hardware status
	 */
	const checkPrinterStatus = async (): Promise<{ online: boolean; message?: string }> => {
		const bridgeUrl = getBridgeUrl();
		try {
			const controller = new AbortController();
			const timeoutId = setTimeout(() => controller.abort(), 3000);
			const res = await fetch(`${bridgeUrl}/status`, { signal: controller.signal });
			clearTimeout(timeoutId);
			return { online: res.ok };
		} catch (e) {
			return { online: false, message: "Принтер недоступен" };
		}
	};

	return {
		fiscalLoading,
		fiscalError,
		fiscalFallbackOpen,
		pendingFiscalInvoice,
		printFiscalReceipt,
		recordNonFiscal,
		printZReport,
		checkPrinterStatus,
	};
}
