<template>
	<div class="pa-3 pos-expense-desk">
		<!-- Top Bar: Title, Context Badges & Global Actions -->
		<div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-3">
			<div class="d-flex align-center ga-2">
				<v-icon color="primary" size="28">mdi-cash-register</v-icon>
				<div>
					<div class="text-h6 font-weight-bold d-flex align-center ga-2">
						{{ __("Расходы кассы") }}
						<v-chip size="small" color="primary" variant="tonal" class="font-weight-bold">
							💵 {{ currentProfileName || __("Загрузка кассы...") }}
						</v-chip>
					</div>
					<div class="text-caption text-grey d-flex align-center ga-2">
						<span v-if="currentShiftName" class="text-success font-weight-medium">
							• <strong>{{ __("Смена") }}:</strong> {{ currentShiftName }}
						</span>
						<span v-else class="text-warning font-weight-medium">
							• {{ __("Смена не открыта (общий режим кассы)") }}
						</span>
						<span>• {{ __("Только операции этой кассы") }}</span>
					</div>
				</div>
			</div>

			<div class="d-flex align-center ga-2">
				<v-btn
					icon="mdi-refresh"
					variant="text"
					density="comfortable"
					:loading="loading"
					@click="fetchData"
					:title="__('Обновить данные')"
				/>
			</div>
		</div>

		<v-row dense class="pos-expense-row">
			<!-- Left Column: Record Expense Form (cols 12, md 5) -->
			<v-col cols="12" md="5" class="pos-col-left">
				<v-card class="pa-4 pos-themed-card h-100 d-flex flex-column overflow-y-auto" elevation="1">
					<div class="d-flex align-center justify-space-between mb-3">
						<div class="text-subtitle-1 font-weight-bold text-primary d-flex align-center ga-2">
							<v-icon size="20" color="primary">mdi-plus-circle-outline</v-icon>
							{{ __("Новый расход") }}
						</div>
						<v-chip size="x-small" color="primary" variant="outlined">
							{{ currentProfileName }}
						</v-chip>
					</div>

					<v-form @submit.prevent="submitExpense" ref="expenseFormRef" class="d-flex flex-column flex-grow-1">
						<!-- Amount Input -->
						<div class="expense-amount-box mb-3">
							<div class="text-caption text-grey mb-1">{{ __("Сумма расхода") }} ({{ currency }})</div>
							<v-text-field
								v-model.number="form.amount"
								type="number"
								min="0.01"
								step="0.01"
								variant="outlined"
								density="comfortable"
								class="expense-amount-input text-h5 font-weight-bold"
								:prefix="currency"
								placeholder="0.00"
								:rules="[amountRule]"
								required
								hide-details="auto"
							/>
							<!-- Quick Add Chips -->
							<div class="d-flex flex-wrap ga-1 mt-2">
								<v-chip
									v-for="amt in [10, 20, 50, 100, 200, 500]"
									:key="amt"
									size="small"
									variant="tonal"
									color="primary"
									class="cursor-pointer"
									@click="addQuickAmount(amt)"
								>
									+{{ amt }}
								</v-chip>
								<v-chip
									size="small"
									variant="text"
									color="error"
									class="cursor-pointer"
									v-if="form.amount > 0"
									@click="form.amount = 0"
								>
									{{ __("Сбросить") }}
								</v-chip>
							</div>
						</div>

						<!-- Category Picker -->
						<div class="mb-3">
							<div class="text-caption text-grey mb-1">{{ __("Категория расхода") }}</div>
							<div class="category-chips-grid">
								<div
									v-for="cat in categories"
									:key="cat.name"
									class="category-chip-item"
									:class="{ 'category-chip-item--active': form.category === cat.category_name }"
									@click="selectCategory(cat)"
								>
									<span class="category-chip-icon">{{ cat.icon || "🏷️" }}</span>
									<span class="category-chip-label">{{ __(cat.category_name) }}</span>
								</div>
							</div>
						</div>

						<!-- Payment Source (Cash till vs Bank only) -->
						<div class="mb-3">
							<div class="text-caption text-grey mb-1">
								{{ __("Источник оплаты (Откуда списать)") }}
							</div>
							<v-select
								v-model="form.source_id"
								:items="paymentSourceOptions"
								item-title="label"
								item-value="id"
								variant="outlined"
								density="compact"
								hide-details
							>
								<template #selection="{ item }">
									<span class="d-flex align-center ga-1 font-weight-medium">
										{{ item.raw.label }}
										<span v-if="item.raw.balance !== undefined" class="text-caption text-grey">
											({{ formatCurrency(item.raw.balance) }})
										</span>
									</span>
								</template>
								<template #item="{ item, props }">
									<v-list-item v-bind="props" :subtitle="formatCurrency(item.raw.balance)">
										<template #prepend>
											<v-icon :color="item.raw.type === 'pos' ? 'success' : 'info'" size="20">
												{{ item.raw.type === "pos" ? "mdi-cash" : "mdi-credit-card-outline" }}
											</v-icon>
										</template>
									</v-list-item>
								</template>
							</v-select>
							<div class="text-caption text-grey mt-1 d-flex align-center ga-1" v-if="isCashSource">
								<v-icon size="14" color="success">mdi-check-decagram</v-icon>
								{{ __("Списание из кассы автоматически уменьшит ожидаемые наличные при закрытии смены") }}
							</div>
						</div>

						<!-- Beneficiary / Employee -->
						<div class="mb-3">
							<div class="text-caption text-grey mb-1">{{ __("Кому выдано / Получатель (Необязательно)") }}</div>
							<v-combobox
								v-model="form.beneficiary_name"
								:items="employeeOptions"
								variant="outlined"
								density="compact"
								hide-details
								:placeholder="__('Сотрудник, курьер или организация')"
								clearable
							/>
						</div>

						<!-- Description / Comment -->
						<div class="mb-4">
							<div class="text-caption text-grey mb-1">{{ __("Примечание / На что потрачено") }}</div>
							<v-text-field
								v-model="form.description"
								variant="outlined"
								density="compact"
								hide-details
								:placeholder="__('Например: Купили 5 упаковок пакетов на оптовке')"
							/>
						</div>

						<v-spacer></v-spacer>

						<!-- Submit Button (compact & sleek) -->
						<div class="d-flex justify-end mt-3">
							<v-btn
								type="submit"
								color="primary"
								density="comfortable"
								:loading="submitting"
								:disabled="!isFormValid || submitting"
								class="expense-submit-btn text-none font-weight-bold"
							>
								<v-icon start size="18">mdi-check</v-icon>
								{{ __("Списать расход") }}
								<span v-if="form.amount > 0" class="ml-1">({{ formatCurrency(form.amount) }})</span>
							</v-btn>
						</div>
					</v-form>
				</v-card>
			</v-col>

			<!-- Right Column: Stats, Full Filter Suite & Isolated History (cols 12, md 7) -->
			<v-col cols="12" md="7" class="pos-col-right">
				<v-card class="pa-4 pos-themed-card h-100 d-flex flex-column overflow-hidden" elevation="1">
					<!-- Top Stat Cards (Isolated to this POS) -->
					<div class="expense-stats-grid mb-3">
						<div class="expense-stat-card expense-stat-card--total">
							<div class="text-caption text-grey">{{ __("Расход за период") }}</div>
							<div class="text-h6 font-weight-bold text-error">
								{{ formatCurrency(summary.period_total || 0) }}
							</div>
							<div class="text-caption text-grey">{{ summary.period_count || 0 }} {{ __("операций") }}</div>
						</div>

						<div class="expense-stat-card expense-stat-card--cash">
							<div class="text-caption text-grey">{{ __("Наличные (Касса)") }}</div>
							<div class="text-h6 font-weight-bold text-warning">
								{{ formatCurrency(summary.cash_total || cashTotal) }}
							</div>
							<div class="text-caption text-grey">{{ __("Списано из ящика кассы") }}</div>
						</div>

						<div class="expense-stat-card expense-stat-card--bank">
							<div class="text-caption text-grey">{{ __("Безналичные (Банк)") }}</div>
							<div class="text-h6 font-weight-bold text-info">
								{{ formatCurrency(summary.bank_total || bankTotal) }}
							</div>
							<div class="text-caption text-grey">{{ __("Оплата картой / банком") }}</div>
						</div>

						<div class="expense-stat-card expense-stat-card--today">
							<div class="text-caption text-grey">{{ __("Всего сегодня") }}</div>
							<div class="text-h6 font-weight-bold text-primary">
								{{ formatCurrency(summary.today_total || 0) }}
							</div>
							<div class="text-caption text-grey">{{ __("За весь день по кассе") }}</div>
						</div>
					</div>

					<!-- Comprehensive Filter Suite -->
					<div class="expense-filter-box pa-3 mb-3 rounded border">
						<!-- Row 1: Period Pills -->
						<div class="d-flex flex-wrap align-center justify-space-between ga-2 mb-2">
							<div class="d-flex flex-wrap align-center ga-1">
								<v-btn
									v-if="currentShiftName"
									size="small"
									:variant="filters.period === 'shift' ? 'flat' : 'outlined'"
									:color="filters.period === 'shift' ? 'primary' : 'default'"
									class="text-none"
									@click="setPeriod('shift')"
								>
									<v-icon start size="16">mdi-clock-time-four-outline</v-icon>
									{{ __("Смена") }}
								</v-btn>

								<v-btn
									size="small"
									:variant="filters.period === 'today' ? 'flat' : 'outlined'"
									:color="filters.period === 'today' ? 'primary' : 'default'"
									class="text-none"
									@click="setPeriod('today')"
								>
									{{ __("Сегодня") }}
								</v-btn>

								<v-btn
									size="small"
									:variant="filters.period === 'yesterday' ? 'flat' : 'outlined'"
									:color="filters.period === 'yesterday' ? 'primary' : 'default'"
									class="text-none"
									@click="setPeriod('yesterday')"
								>
									{{ __("Вчера") }}
								</v-btn>

								<v-btn
									size="small"
									:variant="filters.period === 'week' ? 'flat' : 'outlined'"
									:color="filters.period === 'week' ? 'primary' : 'default'"
									class="text-none"
									@click="setPeriod('week')"
								>
									{{ __("7 дней") }}
								</v-btn>

								<v-btn
									size="small"
									:variant="filters.period === 'month' ? 'flat' : 'outlined'"
									:color="filters.period === 'month' ? 'primary' : 'default'"
									class="text-none"
									@click="setPeriod('month')"
								>
									{{ __("Месяц") }}
								</v-btn>

								<v-btn
									size="small"
									:variant="filters.period === 'all' ? 'flat' : 'outlined'"
									:color="filters.period === 'all' ? 'primary' : 'default'"
									class="text-none"
									@click="setPeriod('all')"
								>
									{{ __("Все") }}
								</v-btn>

								<v-btn
									size="small"
									:variant="filters.period === 'custom' ? 'flat' : 'outlined'"
									:color="filters.period === 'custom' ? 'primary' : 'default'"
									class="text-none"
									@click="toggleCustomPeriod"
								>
									<v-icon start size="16">mdi-calendar-range</v-icon>
									{{ __("Период...") }}
								</v-btn>
							</div>

							<v-btn
								v-if="hasActiveFilters"
								size="small"
								variant="text"
								color="error"
								class="text-none"
								@click="resetFilters"
							>
								<v-icon start size="16">mdi-close</v-icon>
								{{ __("Сбросить фильтры") }}
							</v-btn>
						</div>

						<!-- Custom Date Range Subpanel -->
						<div v-if="filters.period === 'custom'" class="d-flex align-center ga-2 mb-2 pt-2 border-t">
							<v-text-field
								v-model="filters.from_date"
								type="date"
								variant="outlined"
								density="compact"
								hide-details
								:label="__('С даты')"
							/>
							<v-text-field
								v-model="filters.to_date"
								type="date"
								variant="outlined"
								density="compact"
								hide-details
								:label="__('По дату')"
							/>
							<v-btn color="primary" size="small" variant="flat" class="text-none" @click="applyFilters">
								{{ __("Применить") }}
							</v-btn>
						</div>

						<!-- Row 2: Secondary Filters (Category, Source, Employee, Search) -->
						<v-row dense class="mt-1">
							<v-col cols="12" sm="3">
								<v-select
									v-model="filters.category"
									:items="categoryFilterOptions"
									variant="outlined"
									density="compact"
									hide-details
									:label="__('Категория')"
									@update:model-value="applyFilters"
								/>
							</v-col>
							<v-col cols="12" sm="3">
								<v-select
									v-model="filters.source_id"
									:items="sourceFilterOptions"
									variant="outlined"
									density="compact"
									hide-details
									:label="__('Источник')"
									@update:model-value="applyFilters"
								/>
							</v-col>
							<v-col cols="12" sm="3">
								<v-select
									v-model="filters.employee"
									:items="employeeFilterOptions"
									variant="outlined"
									density="compact"
									hide-details
									:label="__('Сотрудник')"
									@update:model-value="applyFilters"
								/>
							</v-col>
							<v-col cols="12" sm="3">
								<v-text-field
									v-model="filters.search"
									variant="outlined"
									density="compact"
									hide-details
									prepend-inner-icon="mdi-magnify"
									:placeholder="__('Поиск...')"
									clearable
									@update:model-value="debounceSearch"
								/>
							</v-col>
						</v-row>
					</div>

					<!-- Category Distribution Pills -->
					<div class="mb-3" v-if="summary.category_breakdown && summary.category_breakdown.length">
						<div class="text-caption text-grey mb-1">{{ __("Распределение по категориям:") }}</div>
						<div class="d-flex flex-wrap ga-2">
							<v-chip
								v-for="cat in summary.category_breakdown"
								:key="cat.category"
								size="small"
								variant="tonal"
								color="primary"
							>
								<span class="mr-1">{{ cat.icon }}</span>
								{{ cat.category }}: <strong>{{ formatCurrency(cat.total) }}</strong> ({{ cat.percent }}%)
							</v-chip>
						</div>
					</div>

					<!-- History Feed Header -->
					<div class="d-flex align-center justify-space-between mb-2">
						<div class="text-subtitle-2 font-weight-bold d-flex align-center ga-1">
							<v-icon size="18" color="primary">mdi-history</v-icon>
							{{ __("Журнал расходов этой кассы") }}
							<span class="text-caption text-grey">({{ filteredExpenses.length }})</span>
						</div>
						<span class="text-caption text-grey">
							{{ getActivePeriodLabel() }}
						</span>
					</div>

					<!-- Expenses Feed / List -->
					<div class="expenses-feed-container flex-grow-1 overflow-y-auto pr-1">
						<v-progress-linear v-if="loading" indeterminate color="primary" class="mb-2" />

						<div v-if="filteredExpenses.length === 0 && !loading" class="text-center py-8 text-grey">
							<v-icon size="48" color="grey-lighten-1" class="mb-2">mdi-cash-remove</v-icon>
							<div class="text-subtitle-1">{{ __("Нет расходов за выбранный период") }}</div>
							<div class="text-caption">{{ __("Все зафиксированные расходы этой кассы появятся здесь") }}</div>
						</div>

						<div v-else class="d-flex flex-column ga-2">
							<div
								v-for="item in filteredExpenses"
								:key="item.name"
								class="expense-row-card"
								:class="{ 'expense-row-card--cancelled': item.docstatus === 2 }"
							>
								<div class="d-flex align-center justify-space-between ga-2">
									<!-- Left: Category, Details & Payee -->
									<div class="d-flex align-center ga-3 flex-grow-1 min-w-0">
										<div class="expense-icon-bubble">
											{{ item.icon || "🏷️" }}
										</div>
										<div class="min-w-0">
											<div class="d-flex align-center ga-2 flex-wrap">
												<span class="font-weight-bold text-subtitle-2 text-truncate">
													{{ __(item.expense_category) }}
												</span>
												<v-chip
													size="x-small"
													:color="item.pos_profile ? 'success' : 'info'"
													variant="tonal"
												>
													{{ item.pos_profile ? `💵 ${item.pos_profile}` : "💳 Банк" }}
												</v-chip>
												<v-chip
													v-if="item.pos_opening_shift"
													size="x-small"
													color="primary"
													variant="outlined"
												>
													{{ item.pos_opening_shift }}
												</v-chip>
												<v-chip
													v-if="item.docstatus === 2"
													size="x-small"
													color="error"
													variant="flat"
												>
													{{ __("Отменено") }}
												</v-chip>
											</div>

											<div class="text-caption text-grey text-truncate mt-1">
												<span v-if="item.employee_name || item.beneficiary_name">
													<strong>{{ item.employee_name || item.beneficiary_name }}</strong> •
												</span>
												<span v-if="item.description">{{ item.description }} • </span>
												<span>{{ item.formatted_date }} {{ item.formatted_time }}</span>
											</div>
										</div>
									</div>

									<!-- Right: Amount & Void button -->
									<div class="d-flex align-center ga-3 flex-shrink-0">
										<div class="text-right">
											<div
												class="text-subtitle-1 font-weight-bold"
												:class="item.docstatus === 2 ? 'text-grey text-decoration-line-through' : 'text-error'"
											>
												-{{ formatCurrency(item.amount) }}
											</div>
											<div class="text-caption text-grey">
												{{ item.name }}
											</div>
										</div>

										<v-btn
											v-if="item.docstatus === 1"
											icon="mdi-close-circle-outline"
											variant="text"
											color="error"
											size="small"
											:title="__('Отменить расход')"
											:loading="cancellingId === item.name"
											@click="confirmCancelExpense(item)"
										/>
									</div>
								</div>
							</div>
						</div>
					</div>

					<!-- Fixed Bottom Summary Row (Visible with few or many rows) -->
					<div class="expense-bottom-sum-row mt-auto pt-2">
						<div class="d-flex align-center justify-space-between flex-wrap ga-2">
							<div class="d-flex align-center flex-wrap ga-2">
								<v-chip size="small" variant="tonal" color="default" class="font-weight-medium">
									{{ __("Всего записей") }}: <strong>{{ filteredExpenses.length }}</strong>
								</v-chip>
								<v-chip
									v-if="feedCashSum > 0"
									size="small"
									variant="tonal"
									color="warning"
									class="font-weight-medium"
								>
									💵 {{ __("Касса") }}: <strong>{{ formatCurrency(feedCashSum) }}</strong>
								</v-chip>
								<v-chip
									v-if="feedBankSum > 0"
									size="small"
									variant="tonal"
									color="info"
									class="font-weight-medium"
								>
									💳 {{ __("Банк") }}: <strong>{{ formatCurrency(feedBankSum) }}</strong>
								</v-chip>
							</div>

							<div class="d-flex align-center ga-2">
								<span class="text-caption text-grey text-uppercase font-weight-bold">
									{{ __("Итого к списанию") }}:
								</span>
								<span class="text-h6 font-weight-black text-error">
									{{ formatCurrency(feedTotalSum) }}
								</span>
							</div>
						</div>
					</div>
				</v-card>
			</v-col>
		</v-row>

		<!-- Confirmation Dialog for Cancellation -->
		<v-dialog v-model="cancelDialogVisible" max-width="400">
			<v-card class="pa-4 pos-themed-card">
				<v-card-title class="text-h6 font-weight-bold text-error px-0 pt-0 d-flex align-center ga-2">
					<v-icon color="error">mdi-alert-circle-outline</v-icon>
					{{ __("Отмена расхода") }}
				</v-card-title>
				<v-card-text class="px-0 py-2">
					{{ __("Вы уверены, что хотите отменить этот расход на сумму") }}
					<strong>{{ formatCurrency(selectedCancelExpense?.amount || 0) }}</strong>?
					<div class="text-caption text-grey mt-2">
						{{ __("Будет отменена связанная бухгалтерская запись и восстановлен баланс кассы.") }}
					</div>
				</v-card-text>
				<v-card-actions class="px-0 pb-0 justify-end ga-2">
					<v-btn variant="text" @click="cancelDialogVisible = false">
						{{ __("Назад") }}
					</v-btn>
					<v-btn
						color="error"
						variant="flat"
						:loading="cancellingId === selectedCancelExpense?.name"
						@click="doCancelExpense"
					>
						{{ __("Да, отменить") }}
					</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from "vue";
import { useUIStore } from "../../../stores/uiStore";
import { useToastStore } from "../../../stores/toastStore";
import { useFormat } from "../../../format";

declare const frappe: any;
const __ = window.__ || ((text: string, _args?: any[]) => text);

const uiStore = useUIStore();
const toastStore = useToastStore();
const { formatCurrency } = useFormat();

const loading = ref(false);
const submitting = ref(false);
const cancellingId = ref<string | null>(null);

const resolvedProfile = ref("");
const resolvedShift = ref("");
const resolvedCompany = ref("");

const currentProfileName = computed(() => {
	return (
		resolvedProfile.value ||
		uiStore.posProfile?.name ||
		frappe.boot?.pos_profile?.name ||
		(typeof frappe.boot?.pos_profile === "string" ? frappe.boot?.pos_profile : "") ||
		""
	);
});

const currentShiftName = computed(() => {
	return resolvedShift.value || uiStore.posOpeningShift?.name || "";
});

const currentCompanyName = computed(() => {
	return resolvedCompany.value || uiStore.posProfile?.company || frappe.defaults?.get_user_default("Company") || "";
});

const currency = ref("TJS");
const categories = ref<any[]>([]);
const paymentSources = ref<any[]>([]);
const employees = ref<any[]>([]);
const recentExpenses = ref<any[]>([]);
const summary = ref<any>({
	period_total: 0,
	period_count: 0,
	today_total: 0,
	cash_total: 0,
	bank_total: 0,
	category_breakdown: [],
});

const form = reactive({
	amount: 0,
	category: "Упаковка и пакеты",
	source_id: "",
	beneficiary_name: "",
	description: "",
});

interface ExpenseFilters {
	period: string;
	from_date: string;
	to_date: string;
	category: string;
	source_id: string;
	employee: string;
	search: string;
}

const filters = reactive<ExpenseFilters>({
	period: "today",
	from_date: "",
	to_date: "",
	category: "all",
	source_id: "all",
	employee: "all",
	search: "",
});

let searchDebounceTimer: any = null;

const cancelDialogVisible = ref(false);
const selectedCancelExpense = ref<any>(null);

const amountRule = (v: any) => (Number(v) > 0 ? true : __("Введите сумму больше 0"));

const isCashSource = computed(() => {
	const src = paymentSources.value.find((s) => s.id === form.source_id);
	return src?.type === "pos";
});

const isFormValid = computed(() => {
	return Number(form.amount) > 0 && !!form.category && !!form.source_id;
});

const paymentSourceOptions = computed(() => {
	return paymentSources.value.map((s) => ({
		id: s.id,
		label: s.label,
		balance: s.balance,
		type: s.type,
		account: s.account,
		pos_profile: s.pos_profile,
	}));
});

const employeeOptions = computed(() => {
	return employees.value.map((e) => e.employee_name || e.name);
});

const categoryFilterOptions = computed(() => {
	const list = [{ value: "all", title: __("Все категории") }];
	categories.value.forEach((c) => {
		list.push({
			value: c.category_name,
			title: `${c.icon || "🏷️"} ${c.category_name}`,
		});
	});
	return list;
});

const sourceFilterOptions = computed(() => {
	const list = [
		{ value: "all", title: __("Все источники") },
		{ value: "cash", title: `💵 ${__("Только касса")} (${currentProfileName.value})` },
		{ value: "bank", title: `💳 ${__("Только банк")}` },
	];
	paymentSources.value.forEach((s) => {
		list.push({
			value: s.id,
			title: s.label,
		});
	});
	return list;
});

const employeeFilterOptions = computed(() => {
	const list = [{ value: "all", title: __("Все сотрудники") }];
	employees.value.forEach((e) => {
		list.push({
			value: e.name,
			title: `👤 ${e.employee_name || e.name}`,
		});
	});
	return list;
});

const cashTotal = computed(() => {
	return recentExpenses.value
		.filter((e) => e.docstatus === 1 && e.pos_profile)
		.reduce((sum, e) => sum + Number(e.amount || 0), 0);
});

const bankTotal = computed(() => {
	return recentExpenses.value
		.filter((e) => e.docstatus === 1 && !e.pos_profile)
		.reduce((sum, e) => sum + Number(e.amount || 0), 0);
});

const feedTotalSum = computed(() => {
	return (recentExpenses.value || [])
		.filter((e) => e.docstatus === 1)
		.reduce((sum, e) => sum + Number(e.amount || 0), 0);
});

const feedCashSum = cashTotal;
const feedBankSum = bankTotal;

const hasActiveFilters = computed(() => {
	return (
		filters.period !== "today" ||
		filters.category !== "all" ||
		filters.source_id !== "all" ||
		filters.employee !== "all" ||
		Boolean(filters.search) ||
		Boolean(filters.from_date) ||
		Boolean(filters.to_date)
	);
});

const filteredExpenses = computed(() => {
	return recentExpenses.value || [];
});

function addQuickAmount(amt: number) {
	form.amount = Math.round(((Number(form.amount) || 0) + amt) * 100) / 100;
}

function selectCategory(cat: any) {
	form.category = cat.category_name;
}

function setPeriod(p: string) {
	filters.period = p;
	applyFilters();
}

function toggleCustomPeriod() {
	if (filters.period === "custom") {
		filters.period = "today";
	} else {
		filters.period = "custom";
	}
	applyFilters();
}

function resetFilters() {
	filters.period = "today";
	filters.from_date = "";
	filters.to_date = "";
	filters.category = "all";
	filters.source_id = "all";
	filters.employee = "all";
	filters.search = "";
	applyFilters();
}

function debounceSearch() {
	if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
	searchDebounceTimer = setTimeout(() => {
		applyFilters();
	}, 300);
}

function getActivePeriodLabel() {
	switch (filters.period) {
		case "shift":
			return __("Текущая смена");
		case "today":
			return __("Сегодня");
		case "yesterday":
			return __("Вчера");
		case "week":
			return __("Последние 7 дней");
		case "month":
			return __("Текущий месяц");
		case "all":
			return __("Все время");
		case "custom":
			return `${filters.from_date || "..."} - ${filters.to_date || "..."}`;
		default:
			return __("Сегодня");
	}
}

async function ensureProfileAndShift() {
	if (uiStore.posProfile?.name) {
		resolvedProfile.value = uiStore.posProfile.name;
		resolvedShift.value = uiStore.posOpeningShift?.name || "";
		resolvedCompany.value = uiStore.posProfile.company || "";
		return;
	}

	// 1. Check opening shift from posawesome API
	try {
		const user = frappe.session?.user || "Administrator";
		const r = await frappe.call("posawesome.posawesome.api.shifts.check_opening_shift", { user });
		if (r?.message) {
			uiStore.setRegisterData(r.message);
			resolvedProfile.value = r.message.pos_profile?.name || r.message.pos_profile || "";
			resolvedShift.value = r.message.pos_opening_shift?.name || r.message.pos_opening_shift || "";
			resolvedCompany.value = r.message.company?.name || r.message.pos_profile?.company || "";
			return;
		}
	} catch (e) {
		console.warn("Could not check opening shift", e);
	}

	// 2. Check frappe.boot
	if (frappe.boot?.pos_profile) {
		const bootName = frappe.boot.pos_profile.name || frappe.boot.pos_profile;
		resolvedProfile.value = bootName;
		return;
	}

	// 3. Fallback: query default active POS profile
	try {
		const res = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "POS Profile",
				filters: { disabled: 0 },
				limit: 1,
				fields: ["name", "company"],
			},
		});
		if (res?.message && res.message.length > 0) {
			resolvedProfile.value = res.message[0].name;
			resolvedCompany.value = res.message[0].company || "";
		}
	} catch (e) {
		console.warn("Could not fetch fallback POS profile", e);
	}
}

async function fetchData() {
	loading.value = true;
	try {
		await ensureProfileAndShift();

		const response = await frappe.call({
			method: "erpnext.accounts.page.expense_desk.expense_desk.get_expense_desk_init_data",
			args: {
				company: currentCompanyName.value || null,
				pos_profile: currentProfileName.value || null,
				pos_opening_shift: currentShiftName.value || null,
				from_pos: 1,
			},
		});

		if (response.message) {
			const data = response.message;
			currency.value = data.currency || "TJS";
			categories.value = data.categories || [];
			paymentSources.value = data.payment_sources || [];
			employees.value = data.employees || [];
			recentExpenses.value = data.recent_expenses || [];
			summary.value = data.summary || summary.value;

			// Auto-select POS cash till as default source if not selected
			if (!form.source_id && paymentSources.value.length) {
				const posSource = paymentSources.value.find((s) => s.type === "pos");
				form.source_id = posSource ? posSource.id : paymentSources.value[0].id;
			}
		}
	} catch (error) {
		console.error("Error fetching expense desk data:", error);
		toastStore.show({
			title: __("Ошибка"),
			message: __("Не удалось загрузить данные расходов"),
			color: "error",
		});
	} finally {
		loading.value = false;
	}
}

async function applyFilters() {
	loading.value = true;
	try {
		const response = await frappe.call({
			method: "erpnext.accounts.page.expense_desk.expense_desk.get_filtered_expenses",
			args: {
				period: filters.period,
				from_date: filters.from_date || null,
				to_date: filters.to_date || null,
				source_id: filters.source_id,
				category: filters.category,
				employee: filters.employee,
				search: filters.search || null,
				company: currentCompanyName.value || null,
				pos_profile: currentProfileName.value || null,
				pos_opening_shift: currentShiftName.value || null,
				from_pos: 1,
			},
		});

		if (response.message) {
			recentExpenses.value = response.message.recent_expenses || [];
			summary.value = response.message.summary || summary.value;
		}
	} catch (error) {
		console.error("Error filtering expenses:", error);
	} finally {
		loading.value = false;
	}
}

async function submitExpense() {
	if (!isFormValid.value || submitting.value) return;

	submitting.value = true;
	try {
		const selectedSource = paymentSources.value.find((s) => s.id === form.source_id);
		const paidFromAccount = selectedSource?.account || null;

		// Resolve employee party if match found
		let partyType: string | null = null;
		let party: string | null = null;
		if (form.beneficiary_name) {
			const emp = employees.value.find(
				(e) => e.employee_name === form.beneficiary_name || e.name === form.beneficiary_name
			);
			if (emp) {
				partyType = "Employee";
				party = emp.name;
			}
		}

		const response = await frappe.call({
			method: "erpnext.accounts.page.expense_desk.expense_desk.record_quick_expense",
			args: {
				category: form.category,
				amount: form.amount,
				paid_from: paidFromAccount,
				pos_profile: currentProfileName.value,
				pos_opening_shift: currentShiftName.value || null,
				created_from_pos: 1,
				description: form.description || null,
				beneficiary_name: form.beneficiary_name || null,
				party_type: partyType,
				party: party,
				company: currentCompanyName.value || null,
			},
		});

		if (response.message) {
			const data = response.message;
			recentExpenses.value = data.recent_expenses || [];
			summary.value = data.summary || summary.value;
			paymentSources.value = data.payment_sources || paymentSources.value;

			toastStore.show({
				title: __("Успешно"),
				message: `${__("Расход")} ${formatCurrency(form.amount)} ${__("зафиксирован")}`,
				color: "success",
			});

			// Reset form fields
			form.amount = 0;
			form.beneficiary_name = "";
			form.description = "";
		}
	} catch (error: any) {
		console.error("Error submitting expense:", error);
		toastStore.show({
			title: __("Ошибка сохранения"),
			message: error?.message || __("Не удалось зафиксировать расход"),
			color: "error",
		});
	} finally {
		submitting.value = false;
	}
}

function confirmCancelExpense(item: any) {
	selectedCancelExpense.value = item;
	cancelDialogVisible.value = true;
}

async function doCancelExpense() {
	if (!selectedCancelExpense.value) return;

	cancellingId.value = selectedCancelExpense.value.name;
	try {
		const response = await frappe.call({
			method: "erpnext.accounts.page.expense_desk.expense_desk.cancel_quick_expense",
			args: {
				expense_name: selectedCancelExpense.value.name,
				company: currentCompanyName.value || null,
				pos_profile: currentProfileName.value || null,
				pos_opening_shift: currentShiftName.value || null,
			},
		});

		if (response.message) {
			const data = response.message;
			recentExpenses.value = data.recent_expenses || [];
			summary.value = data.summary || summary.value;
			paymentSources.value = data.payment_sources || paymentSources.value;

			toastStore.show({
				title: __("Отменено"),
				message: __("Расход успешно отменен"),
				color: "warning",
			});
		}
	} catch (error: any) {
		console.error("Error cancelling expense:", error);
		toastStore.show({
			title: __("Ошибка отмены"),
			message: error?.message || __("Не удалось отменить расход"),
			color: "error",
		});
	} finally {
		cancellingId.value = null;
		cancelDialogVisible.value = false;
		selectedCancelExpense.value = null;
	}
}

watch(
	[() => uiStore.posProfile?.name, () => uiStore.posOpeningShift?.name],
	([newProfile, newShift]) => {
		if (newProfile && (newProfile !== resolvedProfile.value || newShift !== resolvedShift.value)) {
			resolvedProfile.value = newProfile;
			resolvedShift.value = newShift || "";
			fetchData();
		}
	}
);

onMounted(async () => {
	await fetchData();
});
</script>

<style scoped>
.pos-expense-desk {
	height: calc(100dvh - 64px);
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.pos-expense-row {
	flex: 1 1 0;
	min-height: 0;
}

.pos-col-left,
.pos-col-right {
	height: 100%;
	display: flex;
	flex-direction: column;
}

.category-chips-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
	gap: 6px;
	max-height: 180px;
	overflow-y: auto;
	padding-right: 2px;
}

.category-chip-item {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 6px 10px;
	border-radius: var(--pos-radius-sm, 8px);
	border: 1px solid var(--pos-border, rgba(0, 0, 0, 0.12));
	background: var(--pos-surface-variant, #f5f5f5);
	cursor: pointer;
	font-size: 0.78rem;
	user-select: none;
	transition: all 0.15s ease;
}

.category-chip-item:hover {
	border-color: var(--pos-primary, #0097a7);
	background: var(--pos-hover-bg, rgba(0, 151, 167, 0.08));
}

.category-chip-item--active {
	border-color: var(--pos-primary, #0097a7);
	background: var(--pos-primary-container, #e0f7fa);
	color: var(--pos-primary-variant, #00838f);
	font-weight: 600;
}

.category-chip-icon {
	font-size: 1.1rem;
	line-height: 1;
}

.category-chip-label {
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.expense-stats-grid {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 8px;
}

@media (max-width: 960px) {
	.expense-stats-grid {
		grid-template-columns: repeat(2, 1fr);
	}
}

.expense-stat-card {
	padding: 10px 12px;
	border-radius: var(--pos-radius-sm, 10px);
	border: 1px solid var(--pos-border, rgba(0, 0, 0, 0.08));
	background: var(--pos-surface-variant, #fbfbfb);
}

.expense-stat-card--total {
	border-left: 3px solid var(--pos-error, #e86674);
}

.expense-stat-card--cash {
	border-left: 3px solid var(--pos-warning, #ff9800);
}

.expense-stat-card--bank {
	border-left: 3px solid var(--pos-info, #2196f3);
}

.expense-stat-card--today {
	border-left: 3px solid var(--pos-primary, #0097a7);
}

.expense-filter-box {
	background: var(--pos-surface-variant, #f8f9fa);
	border-color: var(--pos-border, rgba(0, 0, 0, 0.08)) !important;
}

.expenses-feed-container {
	flex: 1 1 0;
	min-height: 120px;
	overflow-y: auto;
}

.expense-row-card {
	padding: 10px 14px;
	border-radius: var(--pos-radius-sm, 8px);
	border: 1px solid var(--pos-border, rgba(0, 0, 0, 0.08));
	background: var(--pos-surface, #ffffff);
	transition: background-color 0.15s;
}

.expense-row-card:hover {
	background: var(--pos-surface-variant, #f9f9f9);
}

.expense-row-card--cancelled {
	opacity: 0.55;
	background: var(--pos-surface-variant, #f0f0f0);
}

.expense-icon-bubble {
	width: 36px;
	height: 36px;
	border-radius: 50%;
	background: var(--pos-hover-bg, rgba(0, 0, 0, 0.04));
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 1.25rem;
	flex-shrink: 0;
}

.expense-bottom-sum-row {
	flex-shrink: 0;
	margin-top: auto;
	padding: 10px 14px;
	border-radius: var(--pos-radius-sm, 8px);
	border: 1px solid var(--pos-border, rgba(0, 0, 0, 0.08));
	background: var(--pos-surface-variant, #fcfcfc);
}

.expense-submit-btn {
	border-radius: var(--pos-radius-sm, 8px);
	height: 38px !important;
	padding: 0 20px !important;
	font-size: 0.875rem !important;
}

@media (max-width: 959px) {
	.pos-expense-desk {
		height: auto;
		overflow-y: auto;
		display: block;
	}
	.pos-expense-row {
		height: auto;
	}
	.pos-col-left,
	.pos-col-right {
		height: auto;
		margin-bottom: 16px;
	}
	.expenses-feed-container {
		max-height: 400px;
	}
}
</style>
