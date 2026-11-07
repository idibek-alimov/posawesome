<template>
	<section class="pos-expense-desk pa-4">
		<header class="expense-header">
			<div>
				<h1 class="text-h6">{{ __("Expenses") }}</h1>
				<p class="expense-muted text-body-2" v-if="session.status === 'ready'">
					{{ session.pos_profile }} · {{ __("Shift") }} {{ session.pos_opening_shift }} ·
					{{ currency }}
				</p>
			</div>
			<div class="expense-actions">
				<v-btn variant="text" to="/pos">{{ __("Back to POS") }}</v-btn>
				<v-btn variant="text" :loading="loading" :disabled="busy || offline" @click="fetchData">{{
					__("Refresh")
				}}</v-btn>
				<v-btn
					v-if="session.cash_movement_enabled || legacyPending"
					variant="text"
					to="/cash-movement"
					>{{ __("Cash movements") }}</v-btn
				>
			</div>
		</header>

		<v-alert v-if="offline" type="warning" variant="tonal" class="mb-4" role="status">
			{{
				__(
					"Offline. New expenses need a connection. Keep your input and reconnect to submit or check a result.",
				)
			}}
		</v-alert>
		<v-alert v-if="legacyPending" type="warning" variant="tonal" class="mb-4">
			{{
				__(
					"There are pending cash movements. Review their status before entering the same expense again.",
				)
			}}
			<v-btn variant="text" to="/cash-movement">{{ __("Review pending movements") }}</v-btn>
		</v-alert>

		<div v-if="pendingOperations.length || recoveryError" class="expense-panel mb-4" aria-live="polite">
			<h2 class="text-subtitle-1 mb-2">{{ __("Result needs confirmation") }}</h2>
			<p class="text-body-2 mb-2">
				{{
					__(
						"Check the original request before recording the payment again. Checking does not pay money.",
					)
				}}
			</p>
			<p v-if="recoveryError" role="alert">{{ recoveryError }}</p>
			<div v-for="operation in pendingOperations" :key="operation.id" class="expense-pending">
				<div>
					<strong>{{
						operation.action === RECORD ? __("Record expense") : __("Cancel expense")
					}}</strong>
					<div>
						{{ operation.args.pos_opening_shift || operation.args.expense_name }} ·
						{{ operation.args.paid_from }}
					</div>
					<div v-if="operation.args.amount">
						{{ operation.args.amount }} · {{ operation.args.company }}
					</div>
					<small class="expense-muted">{{ operation.id }}</small>
				</div>
				<div class="expense-actions">
					<v-btn
						variant="outlined"
						:disabled="offline || busy"
						:loading="checking === operation.action"
						@click="checkResult(operation.action)"
						>{{ __("Check result") }}</v-btn
					>
					<v-btn variant="text" :disabled="offline || busy" @click="retryOriginal(operation)">{{
						__("Retry original request")
					}}</v-btn>
				</div>
			</div>
		</div>
		<v-alert v-if="resultMessage" :type="resultType" variant="tonal" class="mb-4" role="status">
			{{ resultMessage }}
			<a
				v-if="resultDocument"
				:href="sourceDocumentUrl(resultDocument)"
				target="_blank"
				rel="noopener"
				>{{ resultDocument.name }}</a
			>
			<v-btn v-if="resultDocument" variant="text" to="/pos">{{
				__("Return to POS and refresh closing totals")
			}}</v-btn>
		</v-alert>

		<v-alert
			v-if="!loading && ['no_shift', 'select_shift'].includes(session.status)"
			type="info"
			variant="tonal"
		>
			{{
				session.status === "select_shift"
					? __("Choose your active register in POS before recording expenses.")
					: __("Open your shift in POS before recording expenses.")
			}}
			<v-btn variant="text" to="/pos">{{ __("Back to POS") }}</v-btn>
		</v-alert>
		<v-alert v-if="loadError" type="error" variant="tonal" class="mb-4" role="alert">
			{{ loadError }}
			<v-btn variant="text" :disabled="offline || busy" @click="fetchData">{{ __("Retry") }}</v-btn>
		</v-alert>
		<v-progress-linear
			v-if="loading"
			indeterminate
			:aria-label="__('Loading expenses...')"
			class="mb-4"
		/>

		<div v-if="session.status === 'ready'" class="expense-layout">
			<section class="expense-panel expense-entry" :aria-label="__('Record expense')">
				<h2 class="text-subtitle-1 mb-4">{{ __("Record expense") }}</h2>
				<v-alert
					v-if="!loading && !loadError && (!categories.length || !paymentSources.length)"
					type="info"
					variant="tonal"
					class="mb-4"
				>
					{{
						__(
							"Expense setup is incomplete. Ask a manager to configure approved sources and category accounts.",
						)
					}}
				</v-alert>
				<p v-else-if="!session.can_record" class="mb-4">
					{{ __("You can view expenses here. Ask a manager for expense recording access.") }}
				</p>
				<v-form @submit.prevent="submitExpense">
					<fieldset :disabled="entryDisabled" class="expense-fieldset">
						<v-select
							v-model="form.category"
							:items="categoryOptions"
							:label="__('Category')"
							variant="outlined"
							density="comfortable"
							:disabled="entryDisabled"
							hide-details="auto"
							class="mb-4"
						/>
						<v-text-field
							v-model="form.amount"
							:label="__('Amount')"
							:suffix="currency"
							type="number"
							inputmode="decimal"
							min="0"
							step="any"
							variant="outlined"
							density="comfortable"
							:disabled="entryDisabled"
							hide-details="auto"
							class="mb-4"
						/>
						<v-select
							v-model="form.source_id"
							:items="paymentSourceOptions"
							:label="__('Paid from')"
							variant="outlined"
							density="comfortable"
							:disabled="entryDisabled"
							hide-details="auto"
							class="mb-2"
						>
							<template #item="{ item, props }"
								><v-list-item v-bind="props" :subtitle="item.raw.account"
							/></template>
						</v-select>
						<p v-if="selectedSource" class="text-caption expense-muted mb-3">
							{{ selectedSource.account }}
						</p>
						<p class="text-caption expense-muted mb-3">
							{{ __("A submitted expense reduces this source's expected shift amount once.") }}
						</p>
						<v-textarea
							v-if="session.note_required"
							v-model="form.description"
							:label="__('Expense note (required by this register)')"
							rows="2"
							variant="outlined"
							:disabled="entryDisabled"
							hide-details="auto"
							class="mb-4"
						/>
						<details class="mb-4">
							<summary>{{ __("Note, recipient and receipt") }}</summary>
							<div class="pt-4">
								<v-textarea
									v-if="!session.note_required"
									v-model="form.description"
									:label="__('Note (optional)')"
									rows="2"
									variant="outlined"
									:disabled="entryDisabled"
									hide-details="auto"
									class="mb-4"
								/>
								<v-text-field
									v-model="form.beneficiary_name"
									:label="__('Recipient (optional)')"
									variant="outlined"
									:disabled="entryDisabled"
									hide-details="auto"
									class="mb-4"
								/>
								<v-file-input
									v-model="receiptFile"
									:label="__('Receipt photo or PDF (optional)')"
									accept="image/*,application/pdf"
									variant="outlined"
									density="comfortable"
									:disabled="entryDisabled || uploading"
									:loading="uploading"
									hide-details="auto"
									@update:model-value="selectReceipt"
								/>
								<p v-if="form.receipt_attachment" class="text-caption mt-2">
									<a
										:href="receiptUrl(form.receipt_attachment)"
										target="_blank"
										rel="noopener"
										>{{ __("View receipt") }}</a
									>
									· {{ __("Private attachment") }}
								</p>
								<p v-if="uploadError" class="text-error text-body-2 mt-2" role="alert">
									{{ uploadError }}
								</p>
							</div>
						</details>
					</fieldset>
					<p v-if="submitError" class="text-error text-body-2 mb-3" role="alert">
						{{ submitError }}
					</p>
					<v-btn
						type="submit"
						color="primary"
						variant="flat"
						block
						:loading="submitting"
						:disabled="entryDisabled || uploading || !!uploadError || !isFormValid"
						>{{ submitting ? __("Submitting expense…") : __("Record expense") }}</v-btn
					>
				</v-form>
				<details class="mt-4 text-body-2">
					<summary>{{ __("Paid personally or not yet paid?") }}</summary>
					<p class="mt-2">
						{{
							__(
								"For personal spending, ask for an Expense Claim. For an unpaid supplier bill, use Purchase Invoice. Record here only money paid from this register.",
							)
						}}
					</p>
					<a v-if="canOpenClaims" href="/app/expense-claim" target="_blank" rel="noopener">{{
						__("Expense Claims")
					}}</a>
					<a
						v-if="canOpenBills"
						class="ml-3"
						href="/app/purchase-invoice"
						target="_blank"
						rel="noopener"
						>{{ __("Purchase Invoices") }}</a
					>
				</details>
			</section>

			<section class="expense-panel expense-history" :aria-label="__('Shift expense history')">
				<div class="expense-header mb-3">
					<h2 class="text-subtitle-1">{{ __("Shift expense history") }}</h2>
					<small class="expense-muted">{{ __("Only this shift's expenses") }}</small>
				</div>
				<div v-if="!loading && !loadError && !offline && historyReady" class="expense-totals mb-4">
					<div>
						<div class="expense-muted text-body-2">{{ __("Paid expenses") }}</div>
						<strong class="text-h6">{{ money(summary.period_total || 0) }}</strong>
						<div class="text-caption expense-muted">
							{{ periodLabel }} · {{ summary.period_count || 0 }} {{ __("expenses") }}
						</div>
						<div v-if="activeFilterLabel" class="text-caption expense-muted">
							{{ activeFilterLabel }}
						</div>
					</div>
					<div>
						<div class="expense-muted text-body-2">{{ __("Cash") }}</div>
						<span>{{ money(summary.cash_total || 0) }}</span>
					</div>
					<div>
						<div class="expense-muted text-body-2">{{ __("Bank and wallets") }}</div>
						<span>{{ money(summary.bank_total || 0) }}</span>
					</div>
				</div>
				<details class="expense-filters mb-3">
					<summary>{{ __("Filter history") }}</summary>
					<div class="expense-filter-grid pt-4">
						<v-select
							v-model="filters.period"
							:items="periods"
							:label="__('Period')"
							variant="outlined"
							density="compact"
							hide-details
							@update:model-value="filterChanged"
						/>
						<v-select
							v-model="filters.category"
							:items="categoryFilterOptions"
							:label="__('Category')"
							variant="outlined"
							density="compact"
							hide-details
							@update:model-value="filterChanged"
						/>
						<v-select
							v-model="filters.source_id"
							:items="sourceFilterOptions"
							:label="__('Paid from')"
							variant="outlined"
							density="compact"
							hide-details
							@update:model-value="filterChanged"
						/>
						<v-select
							v-model="filters.status"
							:items="statuses"
							:label="__('Status')"
							variant="outlined"
							density="compact"
							hide-details
							@update:model-value="filterChanged"
						/>
						<template v-if="filters.period === 'custom'">
							<v-text-field
								v-model="filters.from_date"
								@update:model-value="markHistoryDirty"
								type="date"
								:label="__('From date')"
								variant="outlined"
								density="compact"
								hide-details
							/>
							<v-text-field
								v-model="filters.to_date"
								@update:model-value="markHistoryDirty"
								type="date"
								:label="__('To date')"
								variant="outlined"
								density="compact"
								hide-details
							/>
						</template>
						<v-text-field
							v-model="filters.search"
							:label="__('Search expenses')"
							variant="outlined"
							density="compact"
							hide-details
							clearable
							@update:model-value="debounceSearch"
						/>
						<v-select
							v-if="employees.length"
							v-model="filters.employee"
							:items="employeeOptions"
							:label="__('Recipient')"
							variant="outlined"
							density="compact"
							hide-details
							@update:model-value="filterChanged"
						/>
					</div>
					<div class="expense-actions mt-2">
						<v-btn
							v-if="filters.period === 'custom'"
							variant="text"
							:disabled="offline"
							@click="applyFilters()"
							>{{ __("Apply") }}</v-btn
						><v-btn variant="text" :disabled="offline" @click="resetFilters">{{
							__("Reset filters")
						}}</v-btn>
					</div>
				</details>
				<p v-if="offline" class="expense-muted">
					{{ __("Reconnect and refresh to see confirmed expense totals.") }}
				</p>
				<p v-else-if="!historyReady && !loading && !loadError" class="expense-muted">
					{{ __("Choose dates and apply to see expenses.") }}
				</p>
				<template v-else-if="!loadError && !loading && historyReady">
					<p v-if="!recentExpenses.length" class="expense-muted py-4">
						{{ __("No expenses match these filters.") }}
					</p>
					<div v-for="item in recentExpenses" :key="item.source_id" class="expense-history-row">
						<div class="expense-record-identity">
							<strong>{{ __(item.expense_category) }}</strong>
							<div class="text-body-2 expense-muted">{{ item.paid_from }}</div>
							<div class="text-caption expense-muted">
								{{ item.formatted_date }} {{ item.formatted_time }}
							</div>
							<div v-if="item.docstatus !== 1" class="text-caption">
								{{ statusLabel(item.docstatus) }}
							</div>
						</div>
						<div class="expense-record-amount">
							<strong>{{ money(item.amount) }}</strong
							><v-btn variant="text" size="small" @click="openDetail(item)">{{
								__("Details")
							}}</v-btn>
						</div>
					</div>
					<v-btn v-if="hasMore" variant="text" @click="applyFilters(true)">{{
						__("Load more")
					}}</v-btn>
					<p v-if="recentExpenses.length" class="text-caption expense-muted mt-3">
						{{ __("Shown") }} {{ recentExpenses.length }} / {{ summary.matching_count }} ·
						{{ __("Totals include all matching submitted expenses.") }}
					</p>
				</template>
			</section>
		</div>

		<v-dialog
			v-model="detailVisible"
			max-width="560"
			aria-labelledby="expense-detail-title"
			@after-leave="clearDetail"
		>
			<v-card class="pa-4">
				<h2 id="expense-detail-title" class="text-h6 mb-3">{{ __("Expense details") }}</h2>
				<v-progress-linear v-if="detailLoading" indeterminate />
				<p v-if="detailError" role="alert" class="text-error">
					{{ detailError
					}}<v-btn variant="text" @click="openDetail(selectedExpense)">{{ __("Retry") }}</v-btn>
				</p>
				<template v-if="detail">
					<div class="text-h6">{{ money(detail.amount) }}</div>
					<dl class="expense-detail-list">
						<dt>{{ __("Date") }}</dt>
						<dd>{{ detail.formatted_date || detail.posting_date }}</dd>
						<dt>{{ __("Category") }}</dt>
						<dd>{{ __(detail.expense_category) }}</dd>
						<dt>{{ __("Paid from") }}</dt>
						<dd>{{ detail.paid_from }}</dd>
						<dt>{{ __("Status") }}</dt>
						<dd>{{ statusLabel(detail.docstatus) }}</dd>
						<dt>{{ __("Shift") }}</dt>
						<dd>{{ detail.pos_opening_shift }}</dd>
						<template v-for="review in detail.shift_links?.reviews || []" :key="review.name">
							<dt>{{ __("Shift Review") }}</dt>
							<dd>
								<a v-if="review.url" :href="review.url" target="_blank" rel="noopener">{{
									__(review.status)
								}}</a
								><span v-else>{{ __(review.status) }}</span>
							</dd>
						</template>
						<dt v-if="detail.beneficiary_name">{{ __("Recipient") }}</dt>
						<dd v-if="detail.beneficiary_name">{{ detail.beneficiary_name }}</dd>
						<dt v-if="detail.description">{{ __("Note") }}</dt>
						<dd v-if="detail.description">{{ detail.description }}</dd>
						<dt v-if="detail.cancellation_reason">{{ __("Cancellation reason") }}</dt>
						<dd v-if="detail.cancellation_reason">{{ detail.cancellation_reason }}</dd>
					</dl>
					<a :href="sourceDocumentUrl(detail)" target="_blank" rel="noopener"
						>{{ detail.name }} · {{ __("Open source document") }}</a
					>
					<div v-if="receiptUrl(detail.receipt_attachment)" class="mt-3">
						<a :href="receiptUrl(detail.receipt_attachment)" target="_blank" rel="noopener">{{
							__("View receipt")
						}}</a>
					</div>
					<div v-for="link in accountingLinks" :key="link.url" class="mt-2">
						<a :href="link.url" target="_blank" rel="noopener">{{ link.name }}</a>
					</div>
					<v-btn
						v-if="
							canCancel && detail.docstatus === 1 && detail.source_doctype === 'Quick Expense'
						"
						color="error"
						variant="text"
						class="mt-3"
						:disabled="busy || pendingOperations.length > 0"
						@click="confirmCancel"
						>{{ __("Cancel expense") }}</v-btn
					>
				</template>
				<v-card-actions class="justify-end"
					><v-btn variant="text" @click="detailVisible = false">{{
						__("Close")
					}}</v-btn></v-card-actions
				>
			</v-card>
		</v-dialog>
		<v-dialog
			v-model="cancelVisible"
			max-width="480"
			:persistent="busy"
			aria-labelledby="expense-cancel-title"
		>
			<v-card class="pa-4">
				<h2 id="expense-cancel-title" class="text-h6 mb-3">{{ __("Cancel expense") }}</h2>
				<p class="mb-3">
					{{
						__(
							"Cancellation reverses the linked accounting entry. It does not return physical money. Enter a reason for the audit history.",
						)
					}}
				</p>
				<v-textarea
					v-model="cancelReason"
					:label="__('Cancellation reason')"
					variant="outlined"
					rows="2"
					:disabled="busy"
				/>
				<p v-if="cancelError" class="text-error" role="alert">{{ cancelError }}</p>
				<v-card-actions class="justify-end"
					><v-btn :disabled="busy" @click="cancelVisible = false">{{ __("Back") }}</v-btn
					><v-btn
						color="error"
						:loading="cancelling"
						:disabled="busy || !cancelReason.trim() || offline"
						@click="cancelExpense"
						>{{ __("Cancel expense") }}</v-btn
					></v-card-actions
				>
			</v-card>
		</v-dialog>
	</section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useUIStore } from "../../../stores/uiStore";
import { useFormat } from "../../../format";
import { isOffline } from "../../../../offline/db";
import { getOfflineCashMovements } from "../../../../offline/cash_movements";
import { receiptUrl, uploadExpenseReceipt } from "../../../composables/pos/expenses/receipt";

declare const frappe: any;
const __ = window.__ || ((text: string) => text);
const base = "erpnext.accounts.page.expense_desk.expense_desk.";
const RECORD = "record_quick_expense";
const CANCEL = "cancel_quick_expense";
const uiStore = useUIStore();
const { formatCurrency } = useFormat();
const money = (value: any) => formatCurrency(value, currency.value);
const session = ref<any>({ status: "loading" });
const currency = ref("");
const categories = ref<any[]>([]);
const paymentSources = ref<any[]>([]);
const employees = ref<any[]>([]);
const canCancel = ref(false);
const loading = ref(false);
const loadError = ref("");
const offline = ref(isOffline());
const legacyPending = ref(0);
const submitting = ref(false);
const cancelling = ref(false);
const checking = ref("");
const busy = computed(() => submitting.value || cancelling.value || !!checking.value);
const uploading = ref(false);
const receiptFile = ref<File | null>(null);
const historyReady = ref(false);
const uploadError = ref("");
const submitError = ref("");
const cancelError = ref("");
const recoveryError = ref("");
const pendingOperations = ref<any[]>([]);
const resultMessage = ref("");
const resultDocument = ref<any>(null);
const resultType = ref<"success" | "warning" | "info">("success");
const form = reactive({
	category: "",
	amount: "" as string | number,
	source_id: "",
	description: "",
	beneficiary_name: "",
	receipt_attachment: "",
});
const recentExpenses = ref<any[]>([]);
const summary = ref<any>({});
const hasMore = ref(false);
const filters = reactive({
	period: "shift",
	from_date: "",
	to_date: "",
	category: "all",
	source_id: "all",
	employee: "all",
	search: "",
	status: "submitted",
});
let requestVersion = 0;
let detailVersion = 0;
let timer: ReturnType<typeof setInterval>;
let searchTimer: ReturnType<typeof setTimeout>;
let disposed = false;
let inputScope = "";
let restoredId = "";
let sourceNeedsDefault = true;
const selectedSource = computed(() => paymentSources.value.find((s) => s.id === form.source_id));
const entryDisabled = computed(
	() =>
		busy.value ||
		offline.value ||
		loading.value ||
		!!loadError.value ||
		!session.value.can_record ||
		!!recoveryError.value ||
		pendingOperations.value.length > 0,
);
const isFormValid = computed(
	() =>
		Number.isFinite(Number(form.amount)) &&
		Number(form.amount) > 0 &&
		categories.value.some((c) => c.name === form.category) &&
		!!selectedSource.value &&
		(!session.value.note_required || !!form.description.trim()),
);
const categoryOptions = computed(() =>
	categories.value.map((c) => ({ title: __(c.category_name), value: c.name })),
);
const paymentSourceOptions = computed(() =>
	paymentSources.value.map((s) => ({ title: s.label, value: s.id, account: s.account })),
);
const categoryFilterOptions = computed(() => [
	{ title: __("All categories"), value: "all" },
	...categories.value.map((c) => ({ title: __(c.category_name), value: c.category_name })),
]);
const sourceFilterOptions = computed(() => [
	{ title: __("All sources"), value: "all" },
	{ title: __("Cash"), value: "cash" },
	{ title: __("Bank and wallets"), value: "bank" },
	...paymentSourceOptions.value,
]);
const employeeOptions = computed(() => [
	{ title: __("All recipients"), value: "all" },
	...employees.value.map((e) => ({ title: e.employee_name || e.name, value: e.name })),
]);
const statuses = [
	{ title: __("Submitted"), value: "submitted" },
	{ title: __("All statuses"), value: "all" },
	{ title: __("Cancelled"), value: "cancelled" },
	{ title: __("Draft"), value: "draft" },
];
const periods = [
	{ title: __("Whole shift"), value: "shift" },
	{ title: __("Today within this shift"), value: "today" },
	{ title: __("Yesterday within this shift"), value: "yesterday" },
	{ title: __("Custom dates within this shift"), value: "custom" },
];
const periodLabel = computed(() =>
	filters.period === "custom"
		? `${filters.from_date} — ${filters.to_date}`
		: periods.find((p) => p.value === filters.period)?.title || "",
);
const activeFilterLabel = computed(() =>
	[
		filters.category !== "all" ? __(filters.category) : "",
		filters.source_id !== "all"
			? sourceFilterOptions.value.find((s) => s.value === filters.source_id)?.title
			: "",
		filters.status !== "submitted" ? statuses.find((s) => s.value === filters.status)?.title : "",
		filters.employee !== "all"
			? employeeOptions.value.find((e) => e.value === filters.employee)?.title
			: "",
		filters.search,
	]
		.filter(Boolean)
		.join(" · "),
);
const canOpenClaims = !!frappe.boot?.user?.can_read?.includes("Expense Claim");
const canOpenBills = !!frappe.boot?.user?.can_read?.includes("Purchase Invoice");
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailError = ref("");
const detail = ref<any>(null);
const selectedExpense = ref<any>(null);
const cancelVisible = ref(false);
const cancelReason = ref("");
const accountingLinks = computed(() =>
	(
		[
			["journal_entry", "journal-entry"],
			["payment_entry", "payment-entry"],
			["purchase_invoice", "purchase-invoice"],
		] as [string, string][]
	).flatMap(([field, route]) =>
		detail.value?.[field]
			? [{ name: detail.value[field], url: `/app/${route}/${encodeURIComponent(detail.value[field])}` }]
			: [],
	),
);

function contextArgs() {
	return {
		company: session.value.company,
		pos_profile: session.value.pos_profile,
		pos_opening_shift: session.value.pos_opening_shift,
		from_pos: 1,
	};
}
function readPending() {
	try {
		recoveryError.value = "";
		pendingOperations.value = [RECORD, CANCEL].flatMap((action) => {
			const operation = frappe.expense_requests?.pending(action);
			if (!operation) return [];
			if (!operation.id || !operation.args || typeof operation.args !== "object")
				throw new Error("invalid");
			return [{ ...operation, action }];
		});
	} catch {
		recoveryError.value = __(
			"The saved request cannot be read. Keep this browser's data and ask a manager to review it.",
		);
	}
}
function pollState() {
	offline.value = isOffline();
	readPending();
	legacyPending.value = getOfflineCashMovements().filter((row: any) => {
		try {
			const raw = row.args?.payload || row.payload;
			const payload = typeof raw === "string" ? JSON.parse(raw) : raw;
			return (
				!session.value.pos_opening_shift ||
				!payload?.pos_opening_shift ||
				payload.pos_opening_shift === session.value.pos_opening_shift
			);
		} catch {
			return true;
		}
	}).length;
}
function resetInput() {
	sourceNeedsDefault = true;
	form.amount = "";
	form.category = "";
	form.source_id = "";
	form.description = "";
	form.beneficiary_name = "";
	form.receipt_attachment = "";
	receiptFile.value = null;
	uploadError.value = "";
}
async function fetchData() {
	const version = ++requestVersion;
	loading.value = true;
	loadError.value = "";
	try {
		await frappe.require("/assets/erpnext/js/expense_requests.js");
		readPending();
		const response = await frappe.call({
			method: "posawesome.posawesome.api.expense_context.get_pos_expense_session",
			args: { pos_opening_shift: uiStore.posOpeningShift?.name || null },
		});
		if (disposed || version !== requestVersion) return;
		session.value = response.message || { status: "no_shift" };
		if (session.value.status !== "ready") {
			recentExpenses.value = [];
			paymentSources.value = [];
			summary.value = {};
			return;
		}
		const scope = `${session.value.company}:${session.value.pos_opening_shift}`;
		if (inputScope && inputScope !== scope) {
			resetInput();
			restoredId = "";
			resetFilterValues();
		}
		inputScope = scope;
		const result = await frappe.call({
			method: base + "get_expense_desk_init_data",
			args: { ...contextArgs(), ...filters },
		});
		if (disposed || version !== requestVersion) return;
		if (!result.message) throw new Error(__("Could not load expenses."));
		const data = result.message;
		if (
			data.company !== session.value.company ||
			data.pos_profile !== session.value.pos_profile ||
			data.pos_opening_shift !== session.value.pos_opening_shift
		)
			throw new Error(__("Expense session changed. Refresh before continuing."));
		currency.value = data.currency;
		categories.value = data.categories || [];
		paymentSources.value = data.payment_sources || [];
		employees.value = data.employees || [];
		canCancel.value = !!data.can_cancel;
		setHistory(data);
		const pending = pendingOperations.value.find(
			(p) => p.action === RECORD && p.args.pos_opening_shift === session.value.pos_opening_shift,
		);
		if (pending && restoredId !== pending.id) {
			form.amount = pending.args.amount;
			form.category = pending.args.category;
			form.description = pending.args.description || "";
			form.beneficiary_name = pending.args.beneficiary_name || "";
			form.receipt_attachment = pending.args.receipt_attachment || "";
			form.source_id = paymentSources.value.find((s) => s.account === pending.args.paid_from)?.id || "";
			restoredId = pending.id;
		}
		// Only choose an unambiguous approved Cash source. Never guess a bank wallet.
		const cash = paymentSources.value.filter((s) => s.account_type === "Cash");
		if (!pending && sourceNeedsDefault && paymentSources.value.length) {
			sourceNeedsDefault = false;
			if (!form.source_id && cash.length === 1) form.source_id = cash[0].id;
		} else if (!pending && form.source_id && !selectedSource.value) form.source_id = "";
	} catch (error: any) {
		if (disposed || version !== requestVersion) return;
		loadError.value = error?.message || __("Could not load expenses.");
		paymentSources.value = [];
		canCancel.value = false;
	} finally {
		if (!disposed && version === requestVersion) {
			loading.value = false;
			pollState();
		}
	}
}
function setHistory(data: any, append = false) {
	historyReady.value = true;
	recentExpenses.value = append
		? [...recentExpenses.value, ...(data.recent_expenses || [])]
		: data.recent_expenses || [];
	summary.value = data.summary || {};
	hasMore.value = !!data.has_more;
}
function markHistoryDirty() {
	++requestVersion;
	historyReady.value = false;
	loading.value = false;
}
function filterChanged() {
	++requestVersion;
	if (filters.period !== "custom") void applyFilters();
	else {
		historyReady.value = false;
		recentExpenses.value = [];
		summary.value = {};
		hasMore.value = false;
		loading.value = false;
	}
}
function resetFilterValues() {
	Object.assign(filters, {
		period: "shift",
		from_date: "",
		to_date: "",
		category: "all",
		source_id: "all",
		employee: "all",
		search: "",
		status: "submitted",
	});
}
function resetFilters() {
	resetFilterValues();
	void applyFilters();
}
function debounceSearch() {
	clearTimeout(searchTimer);
	// Invalidate the previous scope immediately, before debounce elapses.
	++requestVersion;
	loading.value = true;
	searchTimer = setTimeout(() => {
		void applyFilters();
	}, 300);
}
async function applyFilters(append = false) {
	if (session.value.status !== "ready" || offline.value) return;
	const version = ++requestVersion;
	loading.value = true;
	try {
		if (
			filters.period === "custom" &&
			(!filters.from_date || !filters.to_date || filters.from_date > filters.to_date)
		)
			throw new Error(__("Choose a valid start and end date."));
		const response = await frappe.call({
			method: base + "get_filtered_expenses",
			args: { ...contextArgs(), ...filters, limit_start: append ? recentExpenses.value.length : 0 },
		});
		if (disposed || version !== requestVersion) return;
		if (!response.message) throw new Error(__("Could not load expenses."));
		loadError.value = "";
		setHistory(response.message, append);
	} catch (error: any) {
		if (disposed || version !== requestVersion) return;
		loadError.value = error?.message || __("Could not load expenses.");
		recentExpenses.value = [];
		hasMore.value = false;
	} finally {
		if (!disposed && version === requestVersion) loading.value = false;
	}
}
async function selectReceipt(value: File | File[] | null) {
	const file = Array.isArray(value) ? value[0] : value;
	if (entryDisabled.value || uploading.value) return;
	uploadError.value = "";
	form.receipt_attachment = "";
	if (!file) return;
	const scope = inputScope;
	uploading.value = true;
	try {
		const url = await uploadExpenseReceipt(file);
		if (!disposed && inputScope === scope) form.receipt_attachment = url;
	} catch (error: any) {
		if (!disposed && inputScope === scope)
			uploadError.value =
				error?.message || __("Receipt upload failed. Your expense has not been submitted.");
	} finally {
		uploading.value = false;
	}
}
function completed(action: string, expense: any) {
	resultDocument.value = { ...expense, source_doctype: "Quick Expense" };
	resultType.value = expense.docstatus === 2 ? "warning" : "success";
	resultMessage.value =
		expense.docstatus === 2
			? __("Expense cancelled. Ask a manager to review the reversal before making another payment.")
			: __("Expense submitted. This source's expected shift amount is reduced once.");
	if (
		action === RECORD &&
		expense.docstatus === 1 &&
		expense.pos_opening_shift === session.value.pos_opening_shift
	) {
		resetInput();
		restoredId = "";
	}
	resultMessage.value += ` ${formatCurrency(expense.amount, expense.currency)} · ${expense.paid_from} · ${expense.pos_opening_shift || ""}`;
	submitError.value = "";
	cancelVisible.value = false;
	detailVisible.value = false;
}
async function submitExpense() {
	if (entryDisabled.value || !isFormValid.value || uploading.value || uploadError.value) return;
	submitting.value = true;
	submitError.value = "";
	resultMessage.value = "";
	resultDocument.value = null;
	try {
		const data = await frappe.expense_requests.run(RECORD, {
			category: form.category,
			amount: Number(form.amount),
			paid_from: selectedSource.value.account,
			company: session.value.company,
			pos_profile: session.value.pos_profile,
			pos_opening_shift: session.value.pos_opening_shift,
			created_from_pos: 1,
			description: form.description || null,
			beneficiary_name: form.beneficiary_name || null,
			receipt_attachment: form.receipt_attachment || null,
		});
		completed(RECORD, data.expense);
		await fetchData();
	} catch (error: any) {
		submitError.value = error?.message || __("Could not submit the expense. Your input is retained.");
	} finally {
		submitting.value = false;
		readPending();
	}
}
async function checkResult(action: string) {
	if (busy.value || offline.value) return;
	checking.value = action;
	recoveryError.value = "";
	resultDocument.value = null;
	try {
		const result = await frappe.expense_requests.check(action);
		if (!result) {
			readPending();
			return;
		}
		const terminal =
			action === RECORD
				? ["submitted", "cancelled"].includes(result.status)
				: result.status === "cancelled";
		if (terminal && result.name && result.docstatus === (result.status === "submitted" ? 1 : 2)) {
			completed(action, result);
			await fetchData();
		} else {
			resultType.value = "info";
			resultDocument.value = result.name ? { ...result, source_doctype: "Quick Expense" } : null;
			resultMessage.value =
				result.status === "not_found"
					? __(
							"No recorded result yet. The original request is retained. Retry it when the connection and setup are ready.",
						)
					: __(
							"The request is not complete. Keep the original request and ask a manager to review it.",
						);
		}
	} catch (error: any) {
		resultType.value = "warning";
		resultDocument.value = null;
		resultMessage.value =
			error?.message || __("Could not check the result. The original request is retained.");
	} finally {
		checking.value = "";
		readPending();
	}
}
async function retryOriginal(operation: any) {
	if (busy.value || offline.value) return;
	checking.value = operation.action;
	resultDocument.value = null;
	try {
		const data = await frappe.expense_requests.run(operation.action, operation.args);
		completed(operation.action, data.expense);
		await fetchData();
	} catch (error: any) {
		resultType.value = "warning";
		resultMessage.value =
			error?.message || __("Could not check the result. The original request is retained.");
	} finally {
		checking.value = "";
		readPending();
	}
}
function sourceDocumentUrl(item: any) {
	return `/app/${item.source_doctype === "POS Cash Movement" ? "pos-cash-movement" : "quick-expense"}/${encodeURIComponent(item.name)}`;
}
function statusLabel(status: number) {
	return status === 1 ? __("Submitted") : status === 2 ? __("Cancelled") : __("Draft");
}
async function openDetail(item: any) {
	const version = ++detailVersion;
	selectedExpense.value = item;
	detailVisible.value = true;
	detailLoading.value = true;
	detailError.value = "";
	detail.value = null;
	try {
		const response = await frappe.call({
			method: base + "get_expense_detail",
			args: { expense_name: item.name, source_doctype: item.source_doctype },
		});
		if (!disposed && version === detailVersion && detailVisible.value) {
			if (!response.message) throw new Error(__("Could not load expense details."));
			detail.value = { ...item, ...response.message };
		}
	} catch (error: any) {
		if (version === detailVersion)
			detailError.value = error?.message || __("Could not load expense details.");
	} finally {
		if (version === detailVersion) detailLoading.value = false;
	}
}
function clearDetail() {
	++detailVersion;
	detail.value = null;
}
function refreshFromNative() {
	if (disposed || busy.value || document.visibilityState === "hidden") return;
	void fetchData();
	if (detailVisible.value && selectedExpense.value) void openDetail(selectedExpense.value);
}
function confirmCancel() {
	cancelReason.value = "";
	cancelError.value = "";
	cancelVisible.value = true;
}
async function cancelExpense() {
	if (busy.value || offline.value || !detail.value || !canCancel.value || !cancelReason.value.trim())
		return;
	cancelling.value = true;
	cancelError.value = "";
	try {
		const data = await frappe.expense_requests.run(CANCEL, {
			expense_name: detail.value.name,
			company: session.value.company,
			pos_profile: session.value.pos_profile,
			pos_opening_shift: session.value.pos_opening_shift,
			reason: cancelReason.value.trim(),
			expected_modified: detail.value.modified,
		});
		completed(CANCEL, data.expense);
		await fetchData();
	} catch (error: any) {
		cancelError.value = error?.message || __("Could not cancel the expense. Your reason is retained.");
	} finally {
		cancelling.value = false;
		readPending();
	}
}
watch([() => uiStore.posProfile?.name, () => uiStore.posOpeningShift?.name], () => {
	++requestVersion;
	resetInput();
	session.value = { status: "loading" };
	void fetchData();
});
onMounted(() => {
	void fetchData();
	timer = setInterval(pollState, 1000);
	window.addEventListener("storage", pollState);
	window.addEventListener("online", pollState);
	window.addEventListener("offline", pollState);
	window.addEventListener("focus", refreshFromNative);
});
onBeforeUnmount(() => {
	disposed = true;
	++requestVersion;
	++detailVersion;
	clearInterval(timer);
	clearTimeout(searchTimer);
	window.removeEventListener("storage", pollState);
	window.removeEventListener("online", pollState);
	window.removeEventListener("offline", pollState);
	window.removeEventListener("focus", refreshFromNative);
});
</script>

<style scoped>
.pos-expense-desk {
	max-width: 1400px;
	margin: 0 auto;
	min-width: 0;
	color: rgb(var(--v-theme-on-surface));
}
.expense-header,
.expense-actions,
.expense-pending {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	flex-wrap: wrap;
}
.expense-header {
	margin-bottom: 20px;
}
.expense-actions {
	justify-content: flex-start;
	gap: 4px;
}
.expense-layout {
	display: grid;
	grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
	align-items: start;
	gap: 20px;
}
.expense-panel {
	min-width: 0;
	padding: 20px;
	border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
	border-radius: 6px;
	background: rgb(var(--v-theme-surface));
}
.expense-muted {
	color: rgba(var(--v-theme-on-surface), 0.7);
}
.expense-fieldset {
	border: 0;
	margin: 0;
	padding: 0;
	min-width: 0;
}
.expense-totals {
	display: flex;
	flex-wrap: wrap;
	align-items: baseline;
	gap: 16px 28px;
	padding-bottom: 16px;
	border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.expense-filter-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 12px;
}
.expense-history-row {
	display: flex;
	justify-content: space-between;
	gap: 16px;
	padding: 14px 0;
	border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.expense-record-identity {
	min-width: 0;
	overflow-wrap: anywhere;
}
.expense-record-amount {
	display: flex;
	align-items: flex-end;
	flex-direction: column;
	flex-shrink: 0;
	font-variant-numeric: tabular-nums;
}
.expense-detail-list {
	display: grid;
	grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
	gap: 8px 16px;
	margin: 16px 0;
}
.expense-detail-list dt {
	opacity: 0.7;
}
.expense-detail-list dd {
	margin: 0;
	overflow-wrap: anywhere;
	white-space: pre-wrap;
}
.expense-pending {
	padding: 12px 0;
	overflow-wrap: anywhere;
}
.pos-expense-desk :deep(.v-input),
.pos-expense-desk :deep(.v-field) {
	min-width: 0;
}
.pos-expense-desk a {
	color: rgb(var(--v-theme-primary));
	overflow-wrap: anywhere;
}
.pos-expense-desk :deep(.v-btn) {
	text-transform: none;
	letter-spacing: normal;
}
summary {
	cursor: pointer;
	min-height: 40px;
	padding: 8px 0;
}
@media (max-width: 850px) {
	.expense-layout {
		grid-template-columns: minmax(0, 1fr);
	}
	.expense-panel {
		padding: 16px;
	}
}
@media (max-width: 480px) {
	.expense-filter-grid {
		grid-template-columns: minmax(0, 1fr);
	}
	.expense-record-amount {
		max-width: 44%;
		overflow-wrap: anywhere;
		flex-shrink: 1;
	}
}
</style>
