import { isOffline } from "./db";
import {
	claimRetryableQueueEntries,
	clearWriteQueueEntries,
	deleteWriteQueueEntryByIndex,
	enqueueWriteQueueEntry,
	getQueuedPayloadCount,
	getQueuedPayloadSnapshots,
	markWriteQueueEntryFailed,
	markWriteQueueEntrySynced,
	type OfflineEntityType,
} from "./writeQueue";

type AnyRecord = Record<string, any>;
const movementMessage = (message: string, args: string[] = []) =>
	typeof __ === "function"
		? __(message, args)
		: message.replace(
				/\{(\d+)\}/g,
				(_, index) => args[Number(index)] || "",
			);

const CASH_MOVEMENT_ENTITY: OfflineEntityType = "cash_movement";

const CREATE_EXPENSE_METHOD =
	"posawesome.posawesome.api.cash_movement.service.create_pos_expense";
const CREATE_DEPOSIT_METHOD =
	"posawesome.posawesome.api.cash_movement.service.create_cash_deposit";

export async function saveOfflineCashMovement(entry: AnyRecord) {
	let cleanEntry;
	try {
		cleanEntry = JSON.parse(JSON.stringify(entry));
	} catch (error) {
		console.error("Failed to serialize offline cash movement", error);
		throw error;
	}

	return enqueueWriteQueueEntry(CASH_MOVEMENT_ENTITY, cleanEntry);
}

export function getOfflineCashMovements() {
	return getQueuedPayloadSnapshots(CASH_MOVEMENT_ENTITY);
}

export async function clearOfflineCashMovements() {
	await clearWriteQueueEntries(CASH_MOVEMENT_ENTITY);
}

export async function deleteOfflineCashMovement(index: number) {
	await deleteWriteQueueEntryByIndex(CASH_MOVEMENT_ENTITY, index);
}

export function getPendingOfflineCashMovementCount() {
	return getQueuedPayloadCount(CASH_MOVEMENT_ENTITY);
}

function resolveMethod(entry: AnyRecord) {
	if (entry?.method) {
		return entry.method;
	}
	const args = resolveArgs(entry);
	const payload =
		typeof args.payload === "string"
			? JSON.parse(args.payload)
			: args.payload;
	const movementType = String(payload?.movement_type || "").toLowerCase();
	if (movementType === "deposit") return CREATE_DEPOSIT_METHOD;
	if (movementType === "expense") return CREATE_EXPENSE_METHOD;
	throw new Error(
		movementMessage(
			"The original movement type is missing. Manager review is required.",
		),
	);
}

function resolveArgs(entry: AnyRecord) {
	if (entry?.args?.payload) {
		return entry.args;
	}
	return {
		payload: entry.payload || {},
	};
}

export async function syncOfflineCashMovements() {
	const queue = getOfflineCashMovements();
	if (!queue.length) {
		return { pending: 0, synced: 0 };
	}
	if (isOffline()) {
		return { pending: queue.length, synced: 0 };
	}

	const claimedEntries =
		await claimRetryableQueueEntries(CASH_MOVEMENT_ENTITY);
	if (!claimedEntries.length) {
		return { pending: getPendingOfflineCashMovementCount(), synced: 0 };
	}

	let synced = 0;

	for (const entry of claimedEntries) {
		try {
			const method = resolveMethod(entry.payload);
			if (
				![CREATE_EXPENSE_METHOD, CREATE_DEPOSIT_METHOD].includes(method)
			) {
				throw new Error(
					movementMessage(
						"Unsupported legacy cash movement method. The original request was retained.",
					),
				);
			}
			const args = resolveArgs(entry.payload);
			const payload =
				typeof args.payload === "string"
					? JSON.parse(args.payload)
					: args.payload;
			if (!payload?.client_request_id) {
				throw new Error(
					movementMessage(
						"The original cash movement has no request ID. Manager review is required.",
					),
				);
			}
			const response = await frappe.call({
				method,
				args,
			});
			if (
				response.message?.docstatus !== 1 ||
				!response.message?.name ||
				!response.message?.journal_entry
			) {
				throw new Error(
					response.message?.docstatus === 2
						? movementMessage(
								"The original cash movement {0} was cancelled. Manager review is required.",
								[response.message.name],
							)
						: movementMessage(
								"The cash movement result was not confirmed. Retry the original request.",
							),
				);
			}
			synced += 1;
			await markWriteQueueEntrySynced(
				CASH_MOVEMENT_ENTITY,
				Number(entry.queue_id),
				entry.last_attempt_at,
			);
		} catch (error) {
			console.error("Failed to sync offline cash movement", error);
			await markWriteQueueEntryFailed(
				CASH_MOVEMENT_ENTITY,
				Number(entry.queue_id),
				error,
				entry.last_attempt_at,
			);
		}
	}

	return { pending: getPendingOfflineCashMovementCount(), synced };
}
