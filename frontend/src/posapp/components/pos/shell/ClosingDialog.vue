<template>
	<v-dialog v-model="closingDialog" max-width="1100" persistent scrollable aria-labelledby="closing-dialog-title">
		<v-card class="closing-dialog-card">
			<ClosingHeader
				:profile="dialog_data.pos_profile"
				:cashier="cashierName"
				:opened-at="openedAt"
				:busy="submitting"
				@close="closeDialog"
			/>
			<v-card-text class="closing-body" tabindex="0">
				<v-alert v-if="pendingMessage" type="warning" variant="tonal" class="mb-4">
					{{ pendingMessage }}
					<v-btn
						variant="text"
						:disabled="submitting || overviewLoading"
						@click="refreshOverview"
						>{{ __("Refresh totals") }}</v-btn
					>
				</v-alert>
				<v-alert v-if="overviewError" type="error" variant="tonal" class="mb-4">
					{{ __(overviewError) }}
					<v-btn variant="text" :disabled="submitting" @click="refreshOverview">{{
						__("Try again")
					}}</v-btn>
				</v-alert>
				<div v-if="overviewLoading" class="py-8 text-center" role="status">
					<v-progress-circular indeterminate color="primary" size="24" class="mr-2" />{{
						__("Loading shift totals…")
					}}
				</div>
				<v-alert
					v-if="dialog_data.skipped_printed_invoices?.length"
					type="warning"
					variant="tonal"
					class="mb-4"
				>
					{{ __("These draft invoices are excluded from the closing totals:") }}
					{{ dialog_data.skipped_printed_invoices.map((row) => row.invoice).join(", ") }}
				</v-alert>
				<template v-if="overview && !overviewLoading">
					<PaymentReconciliation
						:payments="dialog_data.payment_reconciliation"
						:currency="overviewCompanyCurrency"
						:hide-expected="hideExpected"
						:busy="submitting"
						:format-currency="formatCurrency"
					/>
					<section class="summary-section" aria-labelledby="closing-sales-title">
						<h3 id="closing-sales-title" class="text-subtitle-1 font-weight-medium">
							{{ __("Shift sales") }}
						</h3>
						<div class="sales-totals">
							<div v-for="metric in salesMetrics" :key="metric.label">
								<span class="text-body-2 text-medium-emphasis">{{ __(metric.label) }}</span>
								<strong>{{ metric.value }}</strong>
							</div>
						</div>
						<p v-if="settlementNote" class="text-caption text-medium-emphasis mt-2">
							{{ settlementNote }}
						</p>
					</section>
					<section
						v-if="salespeople.length"
						class="summary-section"
						aria-labelledby="closing-people-title"
					>
						<h3 id="closing-people-title" class="text-subtitle-1 font-weight-medium mb-2">
							{{ __("Sales by salesperson") }}
						</h3>
						<v-table density="compact" class="salesperson-table">
							<thead>
								<tr>
									<th>{{ __("Salesperson") }}</th>
									<th>{{ __("Sales") }}</th>
									<th>{{ __("Returns") }}</th>
									<th>{{ __("After returns") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="person in salespeople" :key="person.sales_person">
									<td>{{ person.sales_person || __("Unassigned") }}</td>
									<td>
										{{ formatCurrencyWithSymbol(person.sales, overviewCompanyCurrency) }}
									</td>
									<td>
										{{
											formatCurrencyWithSymbol(person.returns, overviewCompanyCurrency)
										}}
									</td>
									<td class="font-weight-medium">
										{{ formatCurrencyWithSymbol(person.total, overviewCompanyCurrency) }}
									</td>
								</tr>
							</tbody>
						</v-table>
					</section>
					<details v-if="!hideExpected" class="summary-section">
						<summary>{{ __("View details") }}</summary>
						<div class="pt-4">
							<section v-if="movements.length" class="mb-4">
								<h3 class="text-subtitle-1 mb-2">{{ __("Money taken out") }}</h3>
								<div
									v-for="movement in movements"
									:key="movement.doctype + movement.name"
									class="movement-row text-body-2"
								>
									<a
										:href="documentLink(movement.doctype, movement.name)"
										target="_blank"
										rel="noopener"
										>{{ movement.name }}</a
									>
									<span
										>{{ __(movement.label) }} ·
										{{ movement.mode_of_payment || movement.account }}</span
									>
									<strong>{{
										formatCurrencyWithSymbol(movement.amount, overviewCompanyCurrency)
									}}</strong>
								</div>
								<p class="text-caption text-medium-emphasis mt-2">
									{{
										__(
											"Only withdrawals from this register's accounts reduce its expected amounts.",
										)
									}}
								</p>
							</section>
							<ShiftOverview
								:loading="overviewLoading"
								:primary-insights="[]"
								:secondary-insights="[]"
								:multi-currency-totals="multiCurrencyTotals"
								:credit-invoices-by-currency="creditInvoicesByCurrency"
								:returns-by-currency="returnsByCurrency"
								:change-returned-rows="changeReturnedRows"
								:cash-expected-by-currency="cashExpectedByCurrency"
								:cash-movement-summary="cashMovementSummary"
								:loyalty-redemption-summary="loyaltyRedemptionSummary"
								:loyalty-redemption-by-currency="loyaltyRedemptionByCurrency"
								:customer-credit-redeemed-summary="customerCreditRedeemedSummary"
								:customer-credit-redeemed-by-currency="customerCreditRedeemedByCurrency"
								:payments-by-mode="paymentsByMode"
								:overview-company-currency="overviewCompanyCurrency"
								:format-currency-with-symbol="formatCurrencyWithSymbol"
								:should-show-company-equivalent="shouldShowCompanyEquivalent"
								:show-exchange-rates="showExchangeRates"
								:format-exchange-rates="formatExchangeRates"
								:is-cash-mode="isCashMode"
								:overpayment-deduction-for-currency="overpaymentDeductionForCurrency"
							/>
						</div>
					</details>
					<section class="summary-section closing-options">
						<v-checkbox
							v-model="printZReportOption"
							:disabled="submitting"
							hide-details
							density="compact"
							:label="__('Print fiscal Z report')"
						/>
						<v-checkbox
							v-model="autoTransferToSafeOption"
							:disabled="submitting || !canTransfer"
							hide-details
							density="compact"
							:label="__('Transfer counted cash to safe')"
						/>
						<p
							v-if="autoTransferToSafeOption && canTransfer && !hideExpected"
							class="text-caption text-medium-emphasis ml-10"
						>
							{{
								__("Transfer {0} to safe; leave {1} in the drawer.", [
									formatCurrencyWithSymbol(transferAmount, overviewCompanyCurrency),
									formatCurrencyWithSymbol(0, overviewCompanyCurrency),
								])
							}}
						</p>
					</section>
				</template>
			</v-card-text>
			<v-divider />
			<v-card-actions class="pa-4">
				<v-spacer />
				<v-btn variant="text" :disabled="submitting" @click="closeDialog">{{ __("Cancel") }}</v-btn>
				<v-btn
					color="primary"
					variant="flat"
					:loading="submitting"
					:disabled="!canSubmit"
					@click="handleSubmit"
					>{{ __("Close shift") }}</v-btn
				>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>
<script setup>
import { computed, inject, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { useUIStore } from "../../../stores/uiStore.js";
import { useClosingShift } from "../../../composables/pos/closing/useClosingShift";
import { useClosingSummary } from "../../../composables/pos/closing/useClosingSummary";
import { actualAmount } from "../../../composables/pos/closing/closingAmounts";
import { useFormat } from "../../../format";
import { initPromise, isOffline, getQueuedPayloadCount } from "../../../../offline/index";
import ClosingHeader from "../closing/ClosingHeader.vue";
import PaymentReconciliation from "../closing/PaymentReconciliation.vue";
import ShiftOverview from "../closing/ShiftOverview.vue";

const __ = window.__ || ((text) => text);
const uiStore = useUIStore();
const eventBus = inject("eventBus");
const {
	closingDialog,
	dialog_data,
	overview,
	overviewLoading,
	overviewError,
	submitting,
	pos_profile,
	closeDialog,
	fetchOverview,
	submitDialog,
} = useClosingShift(eventBus);
const { formatCurrency, formatFloat, currencySymbol } = useFormat();
const formatCurrencyWithSymbol = (amount, currency) =>
	`${currencySymbol(currency) || currency || ""} ${formatCurrency(amount || 0)}`.trim();
const summary = useClosingSummary(overview, pos_profile, dialog_data, {
	formatCurrencyWithSymbol,
	formatCurrency,
	formatFloat,
	currencySymbol,
	formatCount: (count) => formatFloat(count, 0),
	__,
});
const {
	overviewCompanyCurrency,
	salesSummary,
	returnsSummary,
	salespeople,
	movements,

	multiCurrencyTotals,
	creditInvoicesByCurrency,
	returnsByCurrency,
	changeReturnedRows,
	cashExpectedByCurrency,
	cashMovementSummary,
	loyaltyRedemptionSummary,
	loyaltyRedemptionByCurrency,
	customerCreditRedeemedSummary,
	customerCreditRedeemedByCurrency,
	paymentsByMode,
	shouldShowCompanyEquivalent,
	showExchangeRates,
	formatExchangeRates,
	isCashMode,
	overpaymentDeductionForCurrency,
} = summary;
const hideExpected = computed(() => !!pos_profile.value?.hide_expected_amount);
const cashierName = computed(() =>
	dialog_data.value.user === window.frappe?.session?.user
		? window.frappe?.session?.user_fullname || dialog_data.value.user
		: dialog_data.value.user,
);
const openedAt = computed(() => {
	const value = dialog_data.value.period_start_date;
	return value && window.frappe?.datetime?.str_to_user ? window.frappe.datetime.str_to_user(value) : value;
});
const printZReportOption = ref(true);
const autoTransferToSafeOption = ref(true);
const cashRow = computed(() =>
	dialog_data.value.payment_reconciliation?.find((row) => isCashMode(row.mode_of_payment)),
);
const transferAmount = computed(() => actualAmount(cashRow.value?.closing_amount));
const canTransfer = computed(() => transferAmount.value !== null && transferAmount.value > 0);
const pendingMessage = ref("");
const queueReady = ref(false);
const needsRefresh = ref(false);
const updatePending = () => {
	if (!closingDialog.value) return;
	const pending = ["invoice", "payment", "cash_movement"].some((entity) => getQueuedPayloadCount(entity));
	if (pending || isOffline()) needsRefresh.value = true;
	pendingMessage.value = isOffline()
		? __("Reconnect before closing the shift.")
		: pending
			? __(
					"Sync pending invoices, payments and cash movements, then refresh the totals before closing.",
				)
			: needsRefresh.value
				? __("Refresh totals to include the records that have just synced.")
				: "";
};
const refreshOverview = async () => {
	await fetchOverview(dialog_data.value.pos_opening_shift, pos_profile.value?.currency);
	if (overview.value && !overviewError.value) needsRefresh.value = false;
	updatePending();
};
const salesMetrics = computed(() => [
	{
		label: "Sales",
		value: formatCurrencyWithSymbol(
			salesSummary.value.gross_company_currency_total,
			overviewCompanyCurrency.value,
		),
	},
	{
		label: "Returns",
		value: formatCurrencyWithSymbol(
			returnsSummary.value.company_currency_total,
			overviewCompanyCurrency.value,
		),
	},
	{
		label: "After returns",
		value: formatCurrencyWithSymbol(
			salesSummary.value.net_company_currency_total,
			overviewCompanyCurrency.value,
		),
	},
	{ label: "Number of sales", value: formatFloat(salesSummary.value.sale_invoices_count, 0) },
]);
const settlementNote = computed(() => {
	const ov = overview.value;
	return ov &&
		(ov.credit_invoices?.count ||
			ov.loyalty_redemption?.count ||
			ov.customer_credit_redeemed?.count ||
			dialog_data.value.pos_payments?.length)
		? __(
				"Sales and money received can differ because of credit sales, customer credit, loyalty points and separate payments.",
			)
		: "";
});
const canSubmit = computed(
	() =>
		queueReady.value &&
		!!overview.value &&
		!overviewLoading.value &&
		!overviewError.value &&
		!submitting.value &&
		!pendingMessage.value &&
		(dialog_data.value.payment_reconciliation || []).every(
			(row) => actualAmount(row.closing_amount) !== null,
		),
);
const handleSubmit = () => {
	updatePending();
	if (canSubmit.value)
		submitDialog({
			print_z_report: printZReportOption.value,
			transfer_to_safe: autoTransferToSafeOption.value && canTransfer.value,
		});
};
const documentLink = (doctype, name) =>
	`/app/${doctype.toLowerCase().replaceAll(" ", "-")}/${encodeURIComponent(name)}`;
const open = (data) => {
	submitting.value = false;
	overviewError.value = "";
	needsRefresh.value = false;
	closingDialog.value = true;
	dialog_data.value = data;
	updatePending();
	fetchOverview(data.pos_opening_shift, pos_profile.value?.currency, data.__overview);
};
const submitted = () => {
	submitting.value = false;
	closeDialog();
};
const failed = () => {
	submitting.value = false;
	overviewError.value =
		"Could not close the shift. Check the error and refresh the totals before retrying.";
};
const keydown = (event) => {
	if (event.key === "Escape" && closingDialog.value) closeDialog();
};
let timer;
watch(
	() => uiStore.posProfile,
	(profile) => {
		pos_profile.value = profile || {};
	},
	{ immediate: true },
);
onMounted(() => {
	eventBus?.on("open_ClosingDialog", open);
	eventBus?.on("closing_shift_submitted", submitted);
	eventBus?.on("closing_shift_failed", failed);
	window.addEventListener("keydown", keydown);
	timer = window.setInterval(updatePending, 1500);
	Promise.resolve(initPromise)
		.then(() => {
			queueReady.value = true;
			updatePending();
		})
		.catch(() => {
			overviewError.value = "Could not check pending local records. Reload POS before closing.";
		});
});
onBeforeUnmount(() => {
	eventBus?.off("open_ClosingDialog", open);
	eventBus?.off("closing_shift_submitted", submitted);
	eventBus?.off("closing_shift_failed", failed);
	window.removeEventListener("keydown", keydown);
	window.clearInterval(timer);
});
</script>
<style scoped>
.closing-dialog-card {
	border-radius: 8px;
}
.closing-dialog-card > .v-card-text.closing-body {
	padding: 4px 24px 16px;
}
.summary-section {
	border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
	margin-top: 16px;
	padding-top: 12px;
}
.sales-totals {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 16px;
	margin-top: 10px;
}
.sales-totals strong {
	display: block;
	margin-top: 4px;
	font-size: 1.125rem;
	font-weight: 600;
	font-variant-numeric: tabular-nums;
}
.salesperson-table :deep(th:not(:first-child)),
.salesperson-table :deep(td:not(:first-child)) {
	text-align: end;
	white-space: nowrap;
	font-variant-numeric: tabular-nums;
}
summary {
	cursor: pointer;
	font-size: 0.875rem;
	font-weight: 500;
	width: fit-content;
}
.movement-row {
	display: flex;
	flex-wrap: wrap;
	gap: 8px 16px;
	padding: 6px 0;
}
.movement-row strong {
	margin-inline-start: auto;
}
@media (max-width: 700px) {
	.closing-dialog-card > .v-card-text.closing-body {
		padding: 12px 16px;
	}
	.sales-totals {
		grid-template-columns: repeat(2, 1fr);
	}
}
</style>
