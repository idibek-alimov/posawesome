// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ensureFiscalShift, readFiscalStatus } from "../src/posapp/services/fiscalShift";
import { fiscalRequest } from "../src/posapp/services/fiscalTransport";

vi.mock("../src/posapp/services/fiscalTransport", () => ({ fiscalRequest: vi.fn() }));
const status = (changes = {}) => ({ rc: "SUCCESS", data: { shiftStatus: true, blocked: false, registered: true, onlineStatus: true, queueCount: 0, ...changes } });
const context = { printer_url: "http://192.168.1.102:8002", cashier: "Моҳира" };
beforeEach(() => vi.resetAllMocks());

describe("TP809 fiscal shift preflight", () => {
	it("keeps OFD reachability and queue separate from a ready open shift", async () => {
		vi.mocked(fiscalRequest).mockResolvedValue(status({ onlineStatus: false, queueCount: 2 }));
		expect(await ensureFiscalShift(context)).toMatchObject({ shiftStatus: true, onlineStatus: false, queueCount: 2 });
		expect(fiscalRequest).toHaveBeenCalledTimes(1);
		expect(fiscalRequest).toHaveBeenCalledWith(context, "deviceStatus", expect.objectContaining({ shouldPrintSlip: false }));
	});
	it("opens a closed shift with the verified cashier and rereads status before proceeding", async () => {
		vi.mocked(fiscalRequest).mockResolvedValueOnce(status({ shiftStatus: false })).mockResolvedValueOnce({ rc: "SUCCESS", data: { shiftNumber: 419 } }).mockResolvedValueOnce(status({ shiftNumber: 419 }));
		expect((await ensureFiscalShift(context)).shiftNumber).toBe(419);
		expect(vi.mocked(fiscalRequest).mock.calls.map(c => c[1])).toEqual(["deviceStatus", "openShift", "deviceStatus"]);
		expect(fiscalRequest).toHaveBeenNthCalledWith(2, context, "openShift", { formCode: "OPEN_SHIFT", ffdVersion: "VER_1", shouldPrintSlip: true, cashier: "Моҳира", kktVersion: "1" });
	});
	it("recovers an opening timeout by reading status without opening the shift again", async () => {
		vi.mocked(fiscalRequest).mockResolvedValueOnce(status({ shiftStatus: false })).mockRejectedValueOnce(new Error("timeout")).mockResolvedValueOnce(status());
		await expect(ensureFiscalShift(context)).rejects.toThrow("timeout");
		await ensureFiscalShift(context);
		expect(vi.mocked(fiscalRequest).mock.calls.map(c => c[1])).toEqual(["deviceStatus", "openShift", "deviceStatus"]);
	});
	it("handles another terminal opening the shared printer during preflight", async () => {
		vi.mocked(fiscalRequest).mockResolvedValueOnce(status({ shiftStatus: false })).mockResolvedValueOnce({ rc: "SHIFT_MUST_BE_CLOSED" }).mockResolvedValueOnce(status());
		await expect(ensureFiscalShift(context)).resolves.toMatchObject({ shiftStatus: true });
	});
	it.each([
		[{ blocked: true }, "blocked"], [{ registered: false }, "registered"],
		[{ timestamp: 200000, shiftExpirationTime: 199999 }, "expired"],
		[{ timestamp: 200000, shiftOpeningTime: 100000 }, "expired"],
	])("refuses blocked, unregistered or expired state without closing the device: %o", async (changes, error) => {
		vi.mocked(fiscalRequest).mockResolvedValue(status(changes));
		await expect(ensureFiscalShift(context)).rejects.toThrow(error);
		expect(fiscalRequest).toHaveBeenCalledTimes(1);
	});
	it("rejects incomplete status instead of guessing that the shift is closed", async () => {
		vi.mocked(fiscalRequest).mockResolvedValue({ rc: "SUCCESS", data: {} });
		await expect(readFiscalStatus(context)).rejects.toThrow("incomplete");
	});
	it("does not proceed if the device still reports a closed shift after successful opening", async () => {
		vi.mocked(fiscalRequest).mockResolvedValueOnce(status({ shiftStatus: false })).mockResolvedValueOnce({ rc: "SUCCESS" }).mockResolvedValueOnce(status({ shiftStatus: false }));
		await expect(ensureFiscalShift(context)).rejects.toThrow("not confirmed");
	});
});
