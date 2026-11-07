<template>
	<section class="shift-review-notice" aria-live="polite" :aria-busy="loading">
		<div class="notice-heading">
			<h2 class="text-subtitle-1">{{ __("Your previous shifts") }}</h2>
			<v-btn size="small" variant="text" :disabled="loading || busy || offline" @click="load()">{{
				__("Refresh")
			}}</v-btn>
		</div>
		<p class="text-body-2">
			{{
				__(
					"Enter the money actually available for this opening. Previous differences stay with their original closing and are not added to the opening float.",
				)
			}}
		</p>
		<p v-if="error" role="alert">{{ error }}</p>
		<p v-else-if="offline">{{ __("Reconnect to check previous shift reviews.") }}</p>
		<p v-else-if="loading">{{ __("Loading…") }}</p>
		<template v-else-if="data?.available">
			<div v-if="selected" class="notice-review">
				<strong
					>{{ __("Closed shift") }} {{ selected.closing_shift }} · {{ __(selected.status) }}</strong
				>
				<p v-for="(row, index) in selected.accounts" :key="index">
					{{ row.methods.join(", ") }} · {{ __("Remaining") }}:
					{{ money(row.remaining_amount, selected) }}
				</p>
				<details class="notice-closing-details">
					<summary>
						{{ __("Closing details")
						}}<span v-if="printWarning"> · {{ __("Print result needs confirmation") }}</span>
					</summary>
					<p v-if="selected.cashier_reason">
						{{ __("Cashier explanation") }}: {{ selected.cashier_reason }}
					</p>
					<div v-for="(row, index) in selected.accounts" :key="index" class="notice-amounts">
						<span>{{ row.methods.join(", ") }}</span>
						<span>{{ __("Expected") }}: {{ money(row.expected_amount, selected) }}</span>
						<span>{{ __("Actual") }}: {{ money(row.actual_amount, selected) }}</span>
						<span
							>{{ __("Original difference") }}:
							{{ money(row.original_difference, selected) }}</span
						>
						<strong>{{ __("Remaining") }}: {{ money(row.remaining_amount, selected) }}</strong>
					</div>
					<a v-if="selected.url" :href="selected.url" target="_blank" rel="noopener">{{
						__("Shift Review")
					}}</a>
					<p v-if="transferError" role="alert">{{ transferError }}</p>
					<template v-if="selected.transfer_state">
						<p>{{ __("Safe transfer") }}: {{ __(selected.transfer_state) }}</p>
						<v-btn
							v-if="selected.can_transfer && selected.transfer_state === 'Not recorded'"
							size="small"
							variant="outlined"
							:disabled="busy || offline"
							@click="transfer"
							>{{ __("Check / retry counted cash transfer") }}</v-btn
						>
					</template>
					<p v-if="printWarning">
						{{
							__(
								"The fiscal report result was not confirmed. Check the printer journal or reprint the existing report using the printer's recovery workflow. The ERP shift is already closed.",
							)
						}}
					</p>
				</details>
			</div>
			<details v-if="data.total" class="notice-history">
				<summary>{{ __("Unresolved previous shifts") }}: {{ data.total }}</summary>
				<ul>
					<li v-for="review in reviews" :key="review.review">
						<v-btn variant="text" size="small" :disabled="busy" @click="select(review)"
							>{{ review.closing_shift }} · {{ __(review.status) }}</v-btn
						>
						<div v-for="(row, index) in review.accounts" :key="index">
							{{ row.methods.join(", ") }} · {{ __("Remaining") }}:
							{{ money(row.remaining_amount, review) }}
						</div>
					</li>
				</ul>
				<v-btn
					v-if="data.has_more"
					variant="text"
					size="small"
					:disabled="busy"
					@click="load(true)"
					>{{ __("Load more") }}</v-btn
				>
			</details>
			<p v-else class="text-body-2">
				{{ __("No unresolved differences in your permitted shift history.") }}
			</p>
		</template>
		<p v-else-if="data">
			{{ __("Shift review status is unavailable. Ask a manager to check setup and access.") }}
		</p>
	</section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useUIStore } from "../../../stores/uiStore";

declare const frappe: any;
const props = defineProps<{ posProfile: string }>();
const __ = window.__ || ((text: string) => text);
const store = useUIStore();
const data = ref<any>(null),
	selected = ref<any>(null),
	reviews = ref<any[]>([]);
const loading = ref(false),
	busy = ref(false),
	error = ref(""),
	transferError = ref("");
const offline = ref(!navigator.onLine),
	printWarning = ref(false);
let sequence = 0,
	selectionSequence = 0,
	disposed = false;
const money = (value: any, review: any) =>
	new Intl.NumberFormat(frappe.boot?.lang || "en", {
		minimumFractionDigits: review.currency_precision ?? 2,
		maximumFractionDigits: review.currency_precision ?? 2,
	}).format(Number(value)) +
	" " +
	review.currency;
async function load(more = false) {
	const version = ++sequence;
	data.value = more ? data.value : null;
	if (!more) {
		reviews.value = [];
		selected.value = null;
	}
	error.value = "";
	if (!props.posProfile || offline.value) {
		loading.value = false;
		return;
	}
	loading.value = true;
	try {
		const response = await frappe.call({
			method: "posawesome.posawesome.shift_review.journey.get_register_context",
			args: { pos_profile: props.posProfile, limit_start: more ? reviews.value.length : 0 },
		});
		if (disposed || version !== sequence) return;
		if (typeof response.message?.available !== "boolean")
			throw new Error(__("Could not load previous shift reviews."));
		data.value = response.message;
		reviews.value = more ? [...reviews.value, ...(data.value.reviews || [])] : data.value.reviews || [];
		if (!more && data.value.latest) await select(data.value.latest);
	} catch (failure: any) {
		if (!disposed && version === sequence)
			error.value = failure.message || __("Could not load previous shift reviews.");
	} finally {
		if (version === sequence) loading.value = false;
	}
}
async function select(review: any) {
	const version = sequence;
	const selection = ++selectionSequence;
	selected.value = review;
	transferError.value = "";
	printWarning.value =
		store.lastClosedShift?.user === frappe.session.user &&
		store.lastClosedShift?.name === review.closing_shift &&
		store.lastClosedShift?.print_state === "Unknown";
	try {
		const response = await frappe.call({
			method: "posawesome.posawesome.shift_review.journey.get_closing_status",
			args: { closing_shift: review.closing_shift },
		});
		if (
			!disposed &&
			version === sequence &&
			selection === selectionSequence &&
			selected.value?.review === review.review
		) {
			if (!response.message?.available)
				throw new Error(
					__("Shift review status is unavailable. Ask a manager to check setup and access."),
				);
			selected.value = response.message;
		}
	} catch (failure: any) {
		if (
			!disposed &&
			version === sequence &&
			selection === selectionSequence &&
			selected.value?.review === review.review
		)
			transferError.value = failure.message || __("Could not load previous shift reviews.");
	}
}
async function transfer() {
	const review = selected.value;
	if (busy.value || offline.value || !review?.can_transfer) return;
	const message =
		__(
			"Transfer the original counted cash to the configured Safe? The server checks the original request and will not repeat a completed transfer.",
		) +
		" " +
		money(review.counted_cash, review);
	frappe.confirm(message, async () => {
		if (busy.value || offline.value) return;
		busy.value = true;
		transferError.value = "";
		try {
			const response = await frappe.call(
				"posawesome.posawesome.api.fiscal.transfer_shift_cash_to_safe",
				{ pos_closing_shift_name: review.closing_shift },
			);
			if (!response.message?.success)
				throw new Error(
					response.message?.message ||
						__("The transfer result was not confirmed. Refresh its status before retrying."),
				);
		} catch (failure: any) {
			if (!disposed)
				transferError.value =
					failure.message ||
					__("The transfer result was not confirmed. Refresh its status before retrying.");
		} finally {
			busy.value = false;
			// A read checks the outcome; closure and fiscal printing are never repeated here.
			if (!disposed && selected.value?.review === review.review) {
				const failure = transferError.value;
				await select(review);
				if (selected.value?.transfer_state !== "Complete") transferError.value ||= failure;
			}
		}
	});
}
function connection() {
	offline.value = !navigator.onLine;
	void load();
}
function focus() {
	if (!busy.value) void load();
}
watch(
	() => props.posProfile,
	() => {
		void load();
	},
);
onMounted(() => {
	void load();
	window.addEventListener("online", connection);
	window.addEventListener("offline", connection);
	window.addEventListener("focus", focus);
});
onBeforeUnmount(() => {
	disposed = true;
	++sequence;
	window.removeEventListener("online", connection);
	window.removeEventListener("offline", connection);
	window.removeEventListener("focus", focus);
});
</script>

<style scoped>
.shift-review-notice {
	border: 1px solid var(--pos-border);
	border-radius: 6px;
	padding: 12px;
	margin-bottom: 16px;
	overflow-wrap: anywhere;
}
.notice-heading {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 8px;
}
.notice-amounts {
	display: flex;
	gap: 8px 16px;
	flex-wrap: wrap;
	margin: 8px 0;
}
.notice-history {
	margin-top: 12px;
}
.notice-history ul {
	padding-inline-start: 20px;
}
.notice-history li {
	margin-bottom: 8px;
}
.shift-review-notice :deep(.v-btn) {
	max-width: 100%;
	height: auto;
	min-height: 36px;
}
.shift-review-notice :deep(.v-btn__content) {
	white-space: normal;
}
</style>
