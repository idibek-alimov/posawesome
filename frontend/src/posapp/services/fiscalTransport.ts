declare const frappe: any;
export type FiscalContext = { printer_url?: string; bridge_url?: string; attempt?: string };

export async function fiscalRequest(context: FiscalContext, endpoint: string, payload: any) {
	const request = { ...context, endpoint, payload };
	const desktop = (window as any).electronAPI?.tp809Request;
	if (desktop) return desktop(request);
	const bridge = context.bridge_url;
	if (!bridge) throw new Error("Configure the local TP809 bridge on POS Profile");
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), 20000);
	try {
		const response = await fetch(`${bridge.replace(/\/$/, "")}/fiscal/request`, {
			method: "POST", headers: { "Content-Type": "application/json" },
			body: JSON.stringify(request), signal: controller.signal,
		});
		const result = await response.json();
		if (!response.ok) throw new Error(result.error || `Fiscal HTTP ${response.status}`);
		return result;
	} finally { clearTimeout(timeout); }
}

export async function fiscalContext(doc: any) {
	return (await frappe.call("posawesome.posawesome.api.fiscal.get_fiscal_context", {
		invoice_name: doc.name, doctype: doc.doctype,
	})).message;
}

export async function reprintFiscalReceipt(doc: any) {
	const context = await fiscalContext(doc);
	if (!context.fdNumber) throw new Error("This sale has no confirmed fiscal document");
	const result = await fiscalRequest(context, "getFDByNumber", {
		formCode: "PRINT_FD_BY_NUMBER", ffdVersion: "VER_1", shouldPrintSlip: true, fdNumber: Number(context.fdNumber),
	});
	if (result.rc !== "SUCCESS") throw new Error(result.rc || "Fiscal reprint failed");
	return result;
}
