<template>
	<div class="pa-3">
		<div class="d-flex justify-end mb-3" v-if="pendingOfflineCount > 0">
			<v-btn
				variant="outlined"
				color="warning"
				:loading="syncingOffline"
				:disabled="isOffline()"
				@click="handleSyncOffline"
			>
				{{ __("Sync Offline Cash Movements ({0})", [pendingOfflineCount]) }}
			</v-btn>
		</div>

		<v-alert v-if="errorMessage" type="error" variant="tonal" density="compact" class="mb-3">
			{{ errorMessage }}
		</v-alert>

		<v-alert
			v-if="contextLoaded && !context?.enable_cash_movement"
			type="warning"
			variant="tonal"
			class="mb-3"
		>
			{{ __("Cash Movement is disabled in current POS Profile.") }}
		</v-alert>

		<details v-if="pendingRequests.length" class="mb-3">
			<summary>{{ __("Pending cash movement requests") }}</summary>
			<div v-for="request in pendingRequests" :key="request.queue_id" class="py-2">
				<strong>{{ request.client_request_id }}</strong> · {{ queueStatus(request.status) }}
				<div v-if="request.last_error" class="text-caption">{{ request.last_error }}</div>
				<v-btn
					variant="text"
					:disabled="isOffline() || !request.hasRequestId || !!checkingRequest"
					:loading="checkingRequest === request.queue_id"
					@click="checkRequest(request)"
					>{{ __("Check result") }}</v-btn
				>
				<p v-if="!request.hasRequestId" class="text-caption">
					{{ __("The original cash movement has no request ID. Manager review is required.") }}
				</p>
				<p v-if="requestResults[request.queue_id]" class="text-caption" role="status">
					{{ requestResults[request.queue_id]?.message }}
					<a
						v-if="requestResults[request.queue_id]?.name"
						:href="`/app/pos-cash-movement/${encodeURIComponent(requestResults[request.queue_id]?.name || '')}`"
						target="_blank"
						rel="noopener"
						>{{ requestResults[request.queue_id]?.name }}</a
					>
				</p>
			</div>
		</details>
		<v-row dense>
			<v-col cols="12" md="5">
				<CashMovementForm
					:context="context"
					:submitting="submitting"
					:reset-token="formResetToken"
					:prefill-token="prefillToken"
					:prefill-data="prefillData"
					@submit="handleSubmit"
				/>
			</v-col>
			<v-col cols="12" md="7">
				<CashMovementHistory
					:rows="historyRows"
					:loading="loading"
					:action-loading="actionLoading"
					:allow-cancel="!!context?.allow_cancel_submitted_cash_movement"
					:allow-delete="!!context?.allow_delete_cancelled_cash_movement"
					:selected-status="historyStatus"
					:selected-movement-type="historyMovementType"
					:selected-search-text="historySearchText"
					:pending-offline-count="pendingOfflineCount"
					@refresh="refreshHistory"
					@duplicate="handleDuplicate"
					@cancel="handleCancel"
					@delete="handleDelete"
					@filter-change="handleFilterChange"
				/>
			</v-col>
		</v-row>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { useUIStore } from "../../../stores/uiStore";
import { useToastStore } from "../../../stores/toastStore";
import { useCashMovementValidation } from "../../../composables/pos/cash/useCashMovementValidation";
import { useCashMovement } from "../../../composables/pos/cash/useCashMovement";
import {
	getPendingOfflineCashMovementCount,
	getOfflineCashMovements,
	isOffline,
	saveOfflineCashMovement,
	syncOfflineCashMovements,
} from "../../../../offline";
import CashMovementForm from "./CashMovementForm.vue";
import CashMovementHistory from "./CashMovementHistory.vue";

const __ = window.__ || ((text: string, _args?: any[]) => text);

const router = useRouter();
const uiStore = useUIStore();
const toastStore = useToastStore();

const {
	loading,
	submitting,
	actionLoading,
	context,
	historyRows,
	error,
	loadContext,
	loadHistory,
	cancelMovement,
	deleteMovement,
} = useCashMovement();

const contextLoaded = ref(false);
const syncingOffline = ref(false);
const pendingOfflineCount = ref(0);
const pendingRequests = ref<any[]>([]);
const checkingRequest = ref<number | null>(null);
const requestResults = ref<Record<number, { message: string; name?: string }>>({});
let pendingTimer: ReturnType<typeof setInterval> | undefined;
const historyStatus = ref("");
const historyMovementType = ref("");
const historySearchText = ref("");
const prefillToken = ref(0);
const prefillData = ref<any>(null);
const formResetToken = ref(0);
const errorMessage = computed(() => error.value);

const posProfileName = computed(() => uiStore.posProfile?.name || "");
const openingShiftName = computed(() => uiStore.posOpeningShift?.name || "");

async function initialize() {
	if (!posProfileName.value || !openingShiftName.value) {
		return;
	}
	await loadContext(posProfileName.value, openingShiftName.value);
	contextLoaded.value = true;
	refreshPendingOfflineCount();
	await refreshHistory();
}

async function refreshHistory() {
	if (!openingShiftName.value) {
		return;
	}
	await loadHistory(openingShiftName.value, {
		status: historyStatus.value,
		movementType: historyMovementType.value,
		searchText: historySearchText.value,
	});
}

function refreshPendingOfflineCount() {
	pendingOfflineCount.value = getPendingOfflineCashMovementCount();
	pendingRequests.value = getOfflineCashMovements().flatMap((request: any) => {
		try {
			const stored = request.args?.payload || request.payload;
			const payload = typeof stored === "string" ? JSON.parse(stored) : stored;
			return !openingShiftName.value ||
				!payload?.pos_opening_shift ||
				payload.pos_opening_shift === openingShiftName.value
				? [
						{
							...request,
							hasRequestId: !!payload?.client_request_id,
							client_request_id: payload?.client_request_id || __("Unknown request"),
						},
					]
				: [];
		} catch {
			return [{ ...request, hasRequestId: false, client_request_id: __("Unknown request") }];
		}
	});
}

async function checkRequest(request: any) {
	if (checkingRequest.value || !request.hasRequestId || isOffline()) return;
	checkingRequest.value = request.queue_id;
	try {
		const response = await (window as any).frappe.call({
			method: "posawesome.posawesome.api.cash_movement.service.get_cash_movement_request_outcome",
			args: { client_request_id: request.client_request_id },
		});
		const result = response.message;
		const message =
			result?.status === "submitted" && result.journal_entry
				? __(
						"Movement submitted. Synchronize the original queue; do not record it again. Retained review items need a manager.",
					)
				: result?.status === "cancelled"
					? __("The original movement was cancelled. Keep the request for manager review.")
					: __(
							"No completed result confirmed. The original request is retained; do not enter a duplicate.",
						);
		requestResults.value[request.queue_id] = { message, name: result?.name };
	} catch (error: any) {
		requestResults.value[request.queue_id] = {
			message: error?.message || __("Could not check the result. The original request is retained."),
		};
	} finally {
		checkingRequest.value = null;
	}
}

function queueStatus(status: string) {
	return __(
		(
			{
				pending: "Queued",
				syncing: "Submitting",
				failed: "Failed",
				dead_letter: "Needs manager review",
			} as Record<string, string>
		)[status] || status,
	);
}

onMounted(() => {
	pendingTimer = setInterval(refreshPendingOfflineCount, 1000);
});
onBeforeUnmount(() => {
	clearInterval(pendingTimer);
});

async function handleFilterChange(payload: { status: string; movementType: string; searchText: string }) {
	historyStatus.value = payload?.status || "";
	historyMovementType.value = payload?.movementType || "";
	historySearchText.value = payload?.searchText || "";
	await refreshHistory();
}

async function handleSubmit(payload: any) {
	if (submitting.value) return;
	submitting.value = true;
	try {
		const validation = useCashMovementValidation().validate({ ...payload, context: context.value });
		if (!validation.valid) throw new Error(validation.errors.join("\n"));
		if (!posProfileName.value || !openingShiftName.value)
			throw new Error(__("Open a shift before recording POS expenses."));
		if (
			(payload.movementType === "Expense" && !context.value?.allow_pos_expense) ||
			(payload.movementType === "Deposit" && !context.value?.allow_cash_deposit)
		) {
			throw new Error(__("Selected movement type is not allowed by POS Profile."));
		}

		const requestPayload = {
			pos_profile: posProfileName.value,
			pos_opening_shift: openingShiftName.value,
			posting_date: payload.postingDate,
			amount: payload.amount,
			against_name: payload.againstName,
			source_account: payload.sourceAccount,
			remarks: payload.remarks,
			expense_account: payload.expenseAccount,
			target_account: payload.targetAccount,
			movement_type: payload.movementType,
			client_request_id: `cm-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
		};

		const method =
			payload.movementType === "Deposit"
				? "posawesome.posawesome.api.cash_movement.service.create_cash_deposit"
				: "posawesome.posawesome.api.cash_movement.service.create_pos_expense";
		await saveOfflineCashMovement({ method, args: { payload: requestPayload } });
		formResetToken.value += 1;
		refreshPendingOfflineCount();
		if (!isOffline()) {
			await syncOfflineCashMovements();
			refreshPendingOfflineCount();
		}
		toastStore.show({
			title: pendingOfflineCount.value
				? __("Cash movement saved for confirmation")
				: __("Cash movement submitted"),
			color: pendingOfflineCount.value ? "warning" : "success",
		});
		if (!isOffline()) {
			try {
				await refreshHistory();
			} catch {
				error.value = __("The movement was saved. Refresh the history to see its status.");
			}
		}
	} catch (err: any) {
		toastStore.show({ title: err?.message || __("Failed to submit cash movement"), color: "error" });
	} finally {
		submitting.value = false;
	}
}

function handleDuplicate(row: any) {
	if (!row?.name) return;
	if (row.movement_type === "Expense" && context.value?.shared_expense_ready) {
		router.push("/expenses");
		return;
	}
	prefillData.value = {
		movement_type: row.movement_type,
		amount: row.amount,
		posting_date: row.posting_date,
		against_name: row.against_name,
		source_account: row.source_account,
		remarks: row.remarks,
		expense_account: row.expense_account,
		target_account: row.target_account,
	};
	prefillToken.value += 1;
	toastStore.show({ title: __("Data loaded in form. Review and submit."), color: "info" });
}

async function handleCancel(row: any) {
	if (!row?.name) return;
	try {
		const confirmed = window.confirm(__("Cancel cash movement {0}?", [row.name]));
		if (!confirmed) {
			return;
		}
		const reason =
			row.movement_type === "Expense"
				? window.prompt(__("Reason for cancellation"))?.trim()
				: undefined;
		if (row.movement_type === "Expense" && !reason) return;
		await cancelMovement(row.name, reason);
		toastStore.show({ title: __("Cash movement cancelled"), color: "warning" });
		await refreshHistory();
	} catch (err: any) {
		toastStore.show({ title: err?.message || __("Failed to cancel cash movement"), color: "error" });
	}
}

async function handleDelete(row: any) {
	if (!row?.name) return;
	try {
		const confirmed = window.confirm(__("Delete cancelled cash movement {0}?", [row.name]));
		if (!confirmed) {
			return;
		}
		await deleteMovement(row.name);
		toastStore.show({ title: __("Cash movement deleted"), color: "success" });
		await refreshHistory();
	} catch (err: any) {
		toastStore.show({ title: err?.message || __("Failed to delete cash movement"), color: "error" });
	}
}

async function handleSyncOffline() {
	if (isOffline()) {
		return;
	}
	syncingOffline.value = true;
	try {
		const result = await syncOfflineCashMovements();
		refreshPendingOfflineCount();
		if (result?.synced) {
			toastStore.show({
				title: __("Synced {0} offline cash movement(s).", [result.synced]),
				color: "success",
			});
			await refreshHistory();
			return;
		}
		toastStore.show({
			title: __("No offline cash movement synced."),
			color: "info",
		});
	} catch (err: any) {
		toastStore.show({
			title: err?.message || __("Failed to sync offline cash movements"),
			color: "error",
		});
	} finally {
		syncingOffline.value = false;
	}
}

watch(
	[posProfileName, openingShiftName],
	() => {
		initialize();
	},
	{ immediate: true },
);
</script>
