// @vitest-environment jsdom

import "fake-indexeddb/auto";

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	db,
	getPendingOfflineCashMovementCount,
	initPromise,
	memory,
	clearOfflineCashMovements,
	saveOfflineCashMovement,
	syncOfflineCashMovements,
} from "../src/offline/index";

describe("offline cash movements", () => {
	beforeEach(async () => {
		await initPromise;
		await db.table("write_queue").clear();
		await db.table("queue").clear();
		await db.table("keyval").clear();
		memory.offline_cash_movements = [];
		memory.manual_offline = false;
		localStorage.clear();
		(globalThis as any).frappe = {
			call: vi.fn(),
		};
	});

	it("stores movement in the durable write queue", async () => {
		await saveOfflineCashMovement({
			method: "x",
			args: { payload: { amount: 10, client_request_id: "cm-1" } },
		});

		expect(getPendingOfflineCashMovementCount()).toBe(1);
		const rows = await db.table("write_queue").toArray();
		expect(rows).toHaveLength(1);
		expect(rows[0]).toEqual(
			expect.objectContaining({
				entity_type: "cash_movement",
				status: "pending",
				retry_count: 0,
			}),
		);
	});

	it("syncs queued movements and clears the active queue when online", async () => {
		await saveOfflineCashMovement({
			method: "posawesome.posawesome.api.cash_movement.service.create_pos_expense",
			args: { payload: { amount: 10, client_request_id: "cm-2" } },
		});
		(globalThis as any).frappe.call.mockResolvedValue({
			message: { name: "POS-CM-2", docstatus: 1, journal_entry: "JE-2" },
		});

		const result = await syncOfflineCashMovements();

		expect(result).toEqual({ pending: 0, synced: 1 });
		expect((globalThis as any).frappe.call).toHaveBeenCalledTimes(1);
		expect(getPendingOfflineCashMovementCount()).toBe(0);
	});

	it("does not sync while offline", async () => {
		memory.manual_offline = true;
		await saveOfflineCashMovement({
			args: {
				payload: {
					movement_type: "Deposit",
					amount: 20,
					client_request_id: "cm-3",
				},
			},
		});

		const result = await syncOfflineCashMovements();

		expect(result).toEqual({ pending: 1, synced: 0 });
		expect((globalThis as any).frappe.call).not.toHaveBeenCalled();
		expect(getPendingOfflineCashMovementCount()).toBe(1);
		memory.manual_offline = false;
	});

	it("clear utility empties the queue", async () => {
		await saveOfflineCashMovement({
			args: { payload: { amount: 5, client_request_id: "cm-4" } },
		});
		await clearOfflineCashMovements();
		expect(getPendingOfflineCashMovementCount()).toBe(0);
	});
	it("retains original IDs and payloads across a lost response and retry", async () => {
		const payload = {
			method: "posawesome.posawesome.api.cash_movement.service.create_pos_expense",
			args: {
				payload: {
					amount: 50,
					pos_opening_shift: "ClosedShift",
					client_request_id: "cm-original",
					remarks: "tea",
				},
			},
		};
		await saveOfflineCashMovement(payload);
		(globalThis as any).frappe.call.mockRejectedValueOnce(
			new Error("Lost response"),
		);
		expect(await syncOfflineCashMovements()).toEqual({
			pending: 1,
			synced: 0,
		});
		const failed = await db.table("write_queue").toArray();
		expect(failed[0].status).toBe("failed");
		expect(failed[0].payload).toEqual(payload);
		(globalThis as any).frappe.call.mockResolvedValueOnce({
			message: {
				name: "CM-ORIGINAL",
				docstatus: 1,
				journal_entry: "JE-ORIGINAL",
			},
		});
		expect(await syncOfflineCashMovements()).toEqual({
			pending: 0,
			synced: 1,
		});
		for (const [request] of (globalThis as any).frappe.call.mock.calls) {
			expect(request.method).toBe(payload.method);
			expect(request.args).toEqual(payload.args);
		}
	});

	it("does not treat an HTTP success without a submitted original as posting success", async () => {
		await saveOfflineCashMovement({
			payload: {
				movement_type: "Expense",
				amount: 50,
				client_request_id: "cm-unconfirmed",
			},
		});
		(globalThis as any).frappe.call.mockResolvedValue({
			message: { ok: 1 },
		});
		expect(await syncOfflineCashMovements()).toEqual({
			pending: 1,
			synced: 0,
		});
		const rows = await db.table("write_queue").toArray();
		expect(rows[0].status).toBe("failed");
		expect(rows[0].last_error).toContain("not confirmed");
	});

	it("keeps a cancelled original for manager review without reposting it", async () => {
		await saveOfflineCashMovement({
			payload: {
				movement_type: "Expense",
				amount: 50,
				client_request_id: "cm-cancelled",
			},
		});
		(globalThis as any).frappe.call.mockResolvedValue({
			message: {
				name: "CM-CANCELLED",
				docstatus: 2,
				journal_entry: "JE-OLD",
			},
		});
		expect(await syncOfflineCashMovements()).toEqual({
			pending: 1,
			synced: 0,
		});
		expect(
			(await db.table("write_queue").toArray())[0].last_error,
		).toContain("CM-CANCELLED was cancelled");
	});

	it("preserves serialized old Deposit payloads and their original endpoint", async () => {
		const payload = JSON.stringify({
			movement_type: "Deposit",
			amount: 50,
			client_request_id: "cm-serialized",
		});
		await saveOfflineCashMovement({ args: { payload } });
		(globalThis as any).frappe.call.mockResolvedValue({
			message: {
				name: "CM-DEPOSIT",
				docstatus: 1,
				journal_entry: "JE-TRANSFER",
			},
		});
		expect(await syncOfflineCashMovements()).toEqual({
			pending: 0,
			synced: 1,
		});
		expect((globalThis as any).frappe.call).toHaveBeenCalledWith({
			method: "posawesome.posawesome.api.cash_movement.service.create_cash_deposit",
			args: { payload },
		});
	});

	it("does not invent a new ID for an old financial request missing its identity", async () => {
		const payload = { payload: { movement_type: "Expense", amount: 50 } };
		await saveOfflineCashMovement(payload);
		expect(await syncOfflineCashMovements()).toEqual({
			pending: 1,
			synced: 0,
		});
		expect((globalThis as any).frappe.call).not.toHaveBeenCalled();
		expect((await db.table("write_queue").toArray())[0].payload).toEqual(
			payload,
		);
	});

	it("marks an in-flight request as syncing, not completed", async () => {
		await saveOfflineCashMovement({
			payload: {
				movement_type: "Expense",
				amount: 50,
				client_request_id: "cm-inflight",
			},
		});
		let finish: (value: any) => void;
		const called = new Promise<void>((resolve) => {
			(globalThis as any).frappe.call.mockImplementation(() => {
				resolve();
				return new Promise((r) => {
					finish = r;
				});
			});
		});
		const syncing = syncOfflineCashMovements();
		await called;
		expect((await db.table("write_queue").toArray())[0].status).toBe(
			"syncing",
		);
		expect(getPendingOfflineCashMovementCount()).toBe(1);
		finish!({
			message: {
				name: "CM-INFLIGHT",
				docstatus: 1,
				journal_entry: "JE-INFLIGHT",
			},
		});
		expect(await syncing).toEqual({ pending: 0, synced: 1 });
	});
});
