import { fiscalRequest, type FiscalContext } from "./fiscalTransport";

const tr = (text: string) => (globalThis as any).__?.(text) || text;

export async function readFiscalStatus(context: FiscalContext) {
	const result = await fiscalRequest(context, "deviceStatus", { formCode: "DEVICE_STATUS", shouldPrintSlip: false });
	if (result.rc !== "SUCCESS") throw new Error(result.rc || tr("Could not read fiscal printer status."));
	const data = result.data;
	if (!data || typeof data.shiftStatus !== "boolean" || typeof data.blocked !== "boolean") {
		throw new Error(tr("The printer returned an incomplete status. No fiscal receipt was sent."));
	}
	return data;
}

function assertReady(data: any) {
	if (data.registered === false) throw new Error(tr("The fiscal printer is not registered."));
	if (data.blocked) throw new Error(`${tr("The fiscal printer is blocked.")} ${data.reasonForBlocking || ""}`.trim());
	const expires = Number(data.shiftExpirationTime);
	const timestamp = Number(data.timestamp) || Date.now() / 1000;
	const opened = Number(data.shiftOpeningTime);
	if (data.shiftStatus && ((expires > 0 && expires <= timestamp) || (opened > 0 && timestamp - opened >= 86400))) {
		throw new Error(tr("The fiscal shift has expired. Close it explicitly with a Z report before continuing."));
	}
}

export async function ensureFiscalShift(context: FiscalContext & { cashier?: string }) {
	let data = await readFiscalStatus(context);
	assertReady(data);
	if (data.shiftStatus) return data;
	if (!context.cashier) throw new Error(tr("Verify the active cashier before opening the fiscal shift."));
	// No receipt attempt exists yet. On an open-shift timeout, stop. A later
	// cashier retry reads device status again rather than blindly repeating OPEN_SHIFT.
	const opened = await fiscalRequest(context, "openShift", {
		formCode: "OPEN_SHIFT", ffdVersion: "VER_1", shouldPrintSlip: true,
		cashier: context.cashier, kktVersion: "1",
	});
	// Another terminal may have opened the same device after our first status read.
	if (opened.rc !== "SUCCESS" && opened.rc !== "SHIFT_MUST_BE_CLOSED") {
		throw new Error(opened.rc || tr("Fiscal shift opening was not confirmed. Check printer status before retrying."));
	}
	data = await readFiscalStatus(context);
	assertReady(data);
	if (!data.shiftStatus) throw new Error(tr("Fiscal shift opening was not confirmed. Check printer status before retrying."));
	return data;
}
