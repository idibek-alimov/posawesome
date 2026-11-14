import { ref } from "vue";
import { fiscalContext, fiscalRequest } from "../../../services/fiscalTransport";
import { ensureFiscalShift, readFiscalStatus } from "../../../services/fiscalShift";

declare const frappe: any;
export interface FiscalResult {
	success: boolean; fdNumber?: string | number; fpd?: string; error?: string; raw?: any;
}

export function useFiscalPrinter() {
	const fiscalLoading = ref(false);
	const fiscalError = ref("");
	const fiscalAttemptUnknown = ref(false);
	const fiscalFallbackOpen = ref(false);
	const pendingFiscalInvoice = ref<any>(null);
	const method = (name: string, args: any) => frappe.call(`posawesome.posawesome.api.fiscal.${name}`, args);
	const identity = (doc: any) => ({ invoice_name: doc.name, doctype: doc.doctype || "POS Invoice" });
	const resultKey = (doc: any) => `posa-fiscal-result:${doc.doctype}:${doc.name}`;

	const printFiscalReceipt = async (doc: any): Promise<FiscalResult> => {
		if (fiscalLoading.value) return { success: false, error: "Fiscal request in progress" };
		fiscalLoading.value = true;
		pendingFiscalInvoice.value = { ...doc };
		fiscalAttemptUnknown.value = false;
		try {
			// Save failures recover from the durable result, never by resending a receipt.
			const saved = localStorage.getItem(resultKey(doc));
			let prepared: any;
			let result: any;
			if (saved) {
				fiscalAttemptUnknown.value = true;
				({ prepared, result } = JSON.parse(saved));
			} else {
				const context = (await method("fiscal_checkout_context", identity(doc))).message;
				if (context.completed) return { success: true, fdNumber: context.fdNumber, fpd: context.fpd };
				if (context.status === "Неизвестно") {
					fiscalAttemptUnknown.value = true;
					throw new Error((globalThis as any).__?.("Fiscal result unknown. Check the printer journal and reconcile the existing FD before retrying.") || "Fiscal result unknown. Check the printer journal and reconcile the existing FD before retrying.");
				}
				await ensureFiscalShift(context);
				fiscalAttemptUnknown.value = true;
				prepared = (await method("prepare_fiscal_receipt", identity(doc))).message;
				if (prepared.completed) return { success: true, fdNumber: prepared.fdNumber, fpd: prepared.fpd };
				fiscalAttemptUnknown.value = true;
				result = await fiscalRequest(prepared, "formReceipt", prepared.payload);
				if (result.rc === "SUCCESS") {
					localStorage.setItem(resultKey(doc), JSON.stringify({ prepared, result }));
				}
			}
			if (result.rc !== "SUCCESS") {
				const rejection = await method("record_fiscal_rejection", { ...identity(doc), attempt: prepared.attempt, rc: result.rc || "UNKNOWN" });
				fiscalAttemptUnknown.value = rejection.message?.status !== "Ошибка";
				throw new Error(result.rc || "Fiscal result unknown");
			}
			await method("save_fiscal_data", { ...identity(doc), attempt: prepared.attempt, fiscal_data: result });
			localStorage.removeItem(resultKey(doc));
			fiscalAttemptUnknown.value = false;
			fiscalError.value = "";
			return { success: true, ...result.data, raw: result };
		} catch (error: any) {
			fiscalError.value = error.message || "Fiscal result unknown";
			return { success: false, error: fiscalError.value };
		} finally { fiscalLoading.value = false; }
	};

	const reconcileFiscalReceipt = async (doc: any, fd: string) => {
		if (!/^\d+$/.test(fd) || Number(fd) <= 0) throw new Error("Enter a positive fiscal document number");
		const context = await fiscalContext(doc);
		const result = await fiscalRequest(context, "getFDByNumber", {
			formCode: "PRINT_FD_BY_NUMBER", ffdVersion: "VER_1", shouldPrintSlip: false, fdNumber: Number(fd),
		});
		if (result.rc !== "SUCCESS" || String(result.data?.fdNumber) !== String(Number(fd))) {
			throw new Error("Printer did not confirm the requested fiscal document");
		}
		await method("save_fiscal_data", { ...identity(doc), attempt: context.attempt, fiscal_data: result });
		return result;
	};
	const recordNonFiscal = (doc: any, reason?: string) => method("record_non_fiscal_sale", { ...identity(doc), reason });
	const confirmNoFiscalDocument = async (doc: any) => {
		if (localStorage.getItem(resultKey(doc))) throw new Error("Printer success is already recorded locally. Restore the existing fiscal result.");
		const context = await fiscalContext(doc);
		return method("confirm_unissued_fiscal_attempt", { ...identity(doc), attempt: context.attempt, journal_checked: 1 });
	};
	const printZReport = async (cashier = "Кассир") => {
		try {
			const context = (await method("profile_fiscal_context", {})).message;
			const result = await fiscalRequest(context, "closeShift", { formCode: "CLOSE_SHIFT", ffdVersion: "VER_1", shouldPrintSlip: true, cashier, kktVersion: "1" });
			return result.rc === "SUCCESS";
		} catch { return false; }
	};
	const checkPrinterStatus = async () => {
		try {
			const context = (await method("profile_fiscal_context", {})).message;
			const data = await readFiscalStatus(context);
			return { online: true, ...data };
		} catch (error: any) { return { online: false, message: error.message }; }
	};
	return { fiscalLoading, fiscalError, fiscalAttemptUnknown, fiscalFallbackOpen, pendingFiscalInvoice, printFiscalReceipt,
		reconcileFiscalReceipt, confirmNoFiscalDocument, recordNonFiscal, printZReport, checkPrinterStatus };
}
