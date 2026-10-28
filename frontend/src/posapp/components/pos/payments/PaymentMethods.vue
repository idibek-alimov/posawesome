<template>
	<div v-if="payments && payments.length" class="unified-checkout-flow">
		<!-- 1. Top Payment Mode Pills -->
		<div class="mode-pills-bar" role="tablist">
			<button
				type="button"
				class="mode-pill"
				:class="{ 'mode-pill--active': activeMode === 'cash' }"
				@click="setPaymentMode('cash')"
			>
				<span class="mode-pill__icon">💵</span>
				<span class="mode-pill__title">{{ frappe._("Наличные") }}</span>
			</button>

			<button
				type="button"
				class="mode-pill"
				:class="{ 'mode-pill--active': activeMode === 'bank' }"
				@click="setPaymentMode('bank')"
			>
				<span class="mode-pill__icon">💳</span>
				<span class="mode-pill__title">{{ frappe._("Карта / QR (Банк)") }}</span>
			</button>

			<button
				type="button"
				class="mode-pill"
				:class="{ 'mode-pill--active': activeMode === 'split' }"
				@click="setPaymentMode('split')"
			>
				<span class="mode-pill__icon">🔄</span>
				<span class="mode-pill__title">{{ frappe._("Смешанная") }}</span>
			</button>
		</div>

		<!-- 2. CASH MODE -->
		<div v-if="activeMode === 'cash'" class="pay-card pay-card--cash">
			<div class="cash-input-row">
				<div class="cash-field-wrap">
					<label class="cash-field-label">
						{{ frappe._("ПОЛУЧЕНО ОТ ПОКУПАТЕЛЯ") }}
					</label>
					<div class="cash-input-box">
						<input
							ref="cashInputRef"
							class="cash-input"
							inputmode="decimal"
							:value="cashDisplayValue"
							:placeholder="formatCurrency(payable)"
							@focus="onCashInputFocus"
							@input="onCashInputDirect($event.target.value)"
							@blur="onCashInputBlur"
							@keydown.enter="$event.target.blur()"
						/>
						<span class="cash-currency">{{ currency }}</span>
						<button
							v-if="currentCashAmount > 0"
							type="button"
							class="cash-btn-clear"
							:title="frappe._('Сбросить сумму')"
							@click="clearCashAmount"
						>
							✕
						</button>
						<button
							type="button"
							class="cash-btn-exact"
							:title="frappe._('Заполнить точную сумму (= или Пробел)')"
							@click="setExactCash"
						>
							= {{ frappe._("Точно") }}
						</button>
					</div>
				</div>
			</div>

			<!-- Change Display Badge -->
			<div class="change-status-row">
				<div
					v-if="changeAmount > 0"
					class="change-badge change-badge--give"
				>
					<span class="change-badge__label">{{ frappe._("СДАЧА КЛИЕНТУ") }}:</span>
					<strong class="change-badge__val">{{ formatCurrency(changeAmount) }} {{ currency }}</strong>
				</div>
				<div
					v-else-if="currentCashAmount >= payable && payable > 0"
					class="change-badge change-badge--exact"
				>
					<span>✓ {{ frappe._("Оплата ровно в сумму (без сдачи)") }}</span>
				</div>
				<div
					v-else-if="currentCashAmount > 0 && currentCashAmount < payable"
					class="change-badge change-badge--due"
				>
					<span class="change-badge__label">{{ frappe._("Осталось доплатить") }}:</span>
					<strong class="change-badge__val">{{ formatCurrency(payable - currentCashAmount) }} {{ currency }}</strong>
				</div>
			</div>

			<!-- Somoni Banknote Quick Chips -->
			<div class="banknotes-section">
				<div class="banknotes-title">
					<span>{{ frappe._("Быстрые купюры Сомони (TJS)") }}</span>
					<small class="banknotes-hint">{{ frappe._("Нажмите купюру для сложения сумм") }}</small>
				</div>
				<div class="banknotes-grid">
					<button
						type="button"
						class="chip-banknote chip-banknote--exact"
						@click="setExactCash"
					>
						= {{ frappe._("Точно") }}
					</button>
					<button
						v-for="note in somoniBanknotes"
						:key="note"
						type="button"
						class="chip-banknote"
						@click="addBanknote(note)"
					>
						+{{ note }}
					</button>
				</div>
			</div>
		</div>

		<!-- 3. BANK / QR MODE -->
		<div v-else-if="activeMode === 'bank'" class="pay-card pay-card--bank">
			<div class="bank-header-row">
				<div class="bank-target-total">
					<span class="bank-target-total__label">{{ frappe._("К оплате через терминал / QR") }}:</span>
					<strong class="bank-target-total__val">{{ formatCurrency(payable) }} {{ currency }}</strong>
				</div>
				<div class="bank-no-change-badge">
					<span>✓ {{ frappe._("Сдача: 0.00 (Безналичный расчет)") }}</span>
				</div>
			</div>

			<div class="bank-picker-section">
				<label class="bank-picker-label">{{ frappe._("Выберите банк или платежную систему") }}:</label>
				<div class="bank-grid">
					<button
						v-for="bank in banksList"
						:key="bank.id"
						type="button"
						class="bank-chip"
						:class="{ 'bank-chip--active': selectedBankId === bank.id }"
						:style="{ '--bank-brand-color': bank.color }"
						@click="chooseBank(bank)"
					>
						<span class="bank-chip__indicator" :style="{ backgroundColor: bank.color }"></span>
						<span class="bank-chip__name">{{ bank.label }}</span>
						<span v-if="selectedBankId === bank.id" class="bank-chip__check">✓</span>
					</button>
				</div>
			</div>

			<div class="bank-info-note">
				<v-icon icon="mdi-information-outline" size="18" class="mr-1" />
				<span>{{ frappe._("Платеж привязан к:") }} <strong>{{ currentBankLabel }}</strong>. {{ frappe._("Сумма сразу разнесена на безналичный счет.") }}</span>
			</div>
		</div>

		<!-- 4. SPLIT (MIXED) MODE -->
		<div v-else-if="activeMode === 'split'" class="pay-card pay-card--split">
			<div class="split-rows">
				<!-- Row 1: Cash tender -->
				<div class="split-line">
					<div class="split-line__header">
						<span class="split-line__title">💵 {{ frappe._("Наличная часть") }}</span>
						<button
							type="button"
							class="split-btn-fill"
							@click="fillRemainderCash"
						>
							{{ frappe._("Остаток сюда") }}
						</button>
					</div>
					<div class="cash-input-box cash-input-box--sm">
						<input
							class="cash-input"
							inputmode="decimal"
							:value="currentCashAmount > 0 ? String(currentCashAmount) : ''"
							placeholder="0.00"
							@input="onCashInputDirect($event.target.value)"
						/>
						<span class="cash-currency">{{ currency }}</span>
					</div>
					<!-- Compact quick chips for split cash -->
					<div class="banknotes-grid banknotes-grid--compact">
						<button
							v-for="note in [10, 20, 50, 100, 200]"
							:key="note"
							type="button"
							class="chip-banknote chip-banknote--sm"
							@click="addBanknote(note)"
						>
							+{{ note }}
						</button>
					</div>
				</div>

				<!-- Row 2: Bank tender -->
				<div class="split-line">
					<div class="split-line__header">
						<span class="split-line__title">💳 {{ frappe._("Безналичная часть") }}</span>
						<button
							type="button"
							class="split-btn-fill"
							@click="fillRemainderBank"
						>
							{{ frappe._("Остаток сюда") }}
						</button>
					</div>
					<div class="cash-input-box cash-input-box--sm">
						<input
							class="cash-input"
							inputmode="decimal"
							:value="currentBankAmount > 0 ? String(currentBankAmount) : ''"
							placeholder="0.00"
							@input="onBankInputDirect($event.target.value)"
						/>
						<span class="cash-currency">{{ currency }}</span>
					</div>
					<!-- Bank picker for split -->
					<div class="bank-grid bank-grid--compact">
						<button
							v-for="bank in banksList"
							:key="bank.id"
							type="button"
							class="bank-chip bank-chip--sm"
							:class="{ 'bank-chip--active': selectedBankId === bank.id }"
							:style="{ '--bank-brand-color': bank.color }"
							@click="chooseBank(bank)"
						>
							<span class="bank-chip__name">{{ bank.label }}</span>
						</button>
					</div>
				</div>
			</div>

			<!-- Split Summary Balance -->
			<div class="split-summary-bar">
				<div class="split-summary-item">
					<span>{{ frappe._("Всего внесено") }}:</span>
					<strong>{{ formatCurrency(currentCashAmount + currentBankAmount) }} {{ currency }}</strong>
				</div>
				<div v-if="changeAmount > 0" class="split-summary-item split-summary-item--change">
					<span>{{ frappe._("Сдача клиенту") }}:</span>
					<strong>{{ formatCurrency(changeAmount) }} {{ currency }}</strong>
				</div>
				<div v-else-if="splitRemainingDue > 0" class="split-summary-item split-summary-item--due">
					<span>{{ frappe._("Не хватает") }}:</span>
					<strong>{{ formatCurrency(splitRemainingDue) }} {{ currency }}</strong>
				</div>
				<div v-else class="split-summary-item split-summary-item--ok">
					<span>✓ {{ frappe._("Полная сумма покрыта") }}</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";

const frappe = window.frappe;

const props = defineProps({
	payments: {
		type: Array,
		default: () => [],
	},
	invoiceDoc: {
		type: Object,
		default: () => ({}),
	},
	payable: {
		type: Number,
		default: 0,
	},
	paidChange: {
		type: Number,
		default: 0,
	},
	diffPayment: {
		type: Number,
		default: 0,
	},
	currency: {
		type: String,
		default: "TJS",
	},
	isReturn: {
		type: Boolean,
		default: false,
	},
	currencySymbol: {
		type: Function,
		default: () => "",
	},
	formatCurrency: {
		type: Function,
		default: (val) => String(val || 0),
	},
	isCashLikePayment: {
		type: Function,
		default: () => true,
	},
	showKeyboardShortcuts: Boolean,
});

const emit = defineEmits([
	"update-amount",
	"set-full-amount",
	"set-denomination",
	"mpesa-dialog",
	"request-payment",
	"set-rest-amount",
	"open-gift-card",
]);

// Active payment mode: 'cash' | 'bank' | 'split'
const activeMode = ref("cash");
const cashInputRef = ref(null);
const isEditingCash = ref(false);
const cashTextEntry = ref("");

// Somoni banknote values
const somoniBanknotes = [5, 10, 20, 50, 100, 200, 500];

// Banks list in Tajikistan
const banksList = [
	{ id: "Alif", label: "Alif (Алиф)", color: "#00a651" },
	{ id: "DC", label: "Dushanbe City (DC)", color: "#0072bc" },
	{ id: "Korti Milli", label: "Корти милли", color: "#f39200" },
	{ id: "Other", label: "Другой банк", color: "#64748b" },
];
const selectedBankId = ref("Alif");
const currentBankLabel = computed(() => {
	const b = banksList.find((item) => item.id === selectedBankId.value);
	return b ? b.label : selectedBankId.value;
});

// Identify cash and bank payment lines on the invoice
const cashPayment = computed(() => {
	const list = props.payments || [];
	return list.find((p) => props.isCashLikePayment(p)) || list[0] || null;
});

const bankPayment = computed(() => {
	const list = props.payments || [];
	return list.find((p) => !props.isCashLikePayment(p)) || list[1] || null;
});

const ensureBankLineExists = () => {
	if (!props.invoiceDoc) return;
	if (!Array.isArray(props.invoiceDoc.payments)) {
		props.invoiceDoc.payments = [];
	}
	const hasBank = props.invoiceDoc.payments.some((p) => !props.isCashLikePayment(p));
	if (!hasBank) {
		const newBank = {
			mode_of_payment: "Credit Card",
			amount: 0,
			base_amount: 0,
			type: "Bank",
			default: 0,
			reference_no: selectedBankId.value,
		};
		props.invoiceDoc.payments.push(newBank);
	}
};

const currentCashAmount = computed(() => {
	const p = cashPayment.value;
	return Math.max(Number(p?.amount) || 0, 0);
});

const currentBankAmount = computed(() => {
	const p = bankPayment.value;
	return Math.max(Number(p?.amount) || 0, 0);
});

const cashDisplayValue = computed(() => {
	if (isEditingCash.value) return cashTextEntry.value;
	return currentCashAmount.value > 0 ? String(currentCashAmount.value) : "";
});

// Change calculation
const changeAmount = computed(() => {
	if (activeMode.value === "cash") {
		return Math.max(currentCashAmount.value - props.payable, 0);
	}
	if (activeMode.value === "split") {
		const totalPaid = currentCashAmount.value + currentBankAmount.value;
		return Math.max(totalPaid - props.payable, 0);
	}
	return 0;
});

const splitRemainingDue = computed(() => {
	const totalPaid = currentCashAmount.value + currentBankAmount.value;
	return Math.max(props.payable - totalPaid, 0);
});

// Mode Switching
const setPaymentMode = (mode) => {
	activeMode.value = mode;

	if (mode === "cash") {
		// Cash takes full payable amount
		if (cashPayment.value) {
			emit("set-full-amount", cashPayment.value, props.isReturn);
		}
		if (bankPayment.value) {
			emit("update-amount", bankPayment.value, 0);
		}
		nextTick(() => {
			cashInputRef.value?.focus?.();
			cashInputRef.value?.select?.();
		});
	} else if (mode === "bank") {
		ensureBankLineExists();
		if (cashPayment.value) {
			emit("update-amount", cashPayment.value, 0);
		}
		if (bankPayment.value) {
			emit("set-full-amount", bankPayment.value, props.isReturn);
			bankPayment.value.reference_no = selectedBankId.value;
		}
		if (props.invoiceDoc) {
			props.invoiceDoc.remarks = `Оплата: ${currentBankLabel.value}`;
		}
	} else if (mode === "split") {
		ensureBankLineExists();
	}
};

// Choose bank
const chooseBank = (bank) => {
	selectedBankId.value = bank.id;
	if (bankPayment.value) {
		bankPayment.value.reference_no = bank.id;
	}
	if (props.invoiceDoc) {
		props.invoiceDoc.remarks = `Оплата: ${bank.label}`;
	}
};

// Cash Input handling
const onCashInputFocus = (event) => {
	isEditingCash.value = true;
	cashTextEntry.value = currentCashAmount.value > 0 ? String(currentCashAmount.value) : "";
	event?.target?.select?.();
};

const onCashInputDirect = (val) => {
	cashTextEntry.value = val;
	const num = Number(String(val).replace(/\s/g, "").replace(",", ".")) || 0;
	if (cashPayment.value) {
		emit("update-amount", cashPayment.value, Math.max(num, 0));
	}
};

const onCashInputBlur = () => {
	isEditingCash.value = false;
};

const clearCashAmount = () => {
	if (cashPayment.value) {
		emit("update-amount", cashPayment.value, 0);
	}
	cashTextEntry.value = "";
};

const setExactCash = () => {
	if (cashPayment.value) {
		emit("set-full-amount", cashPayment.value, props.isReturn);
	}
	cashTextEntry.value = String(props.payable);
	nextTick(() => {
		if (cashInputRef.value && document.activeElement === cashInputRef.value) {
			cashInputRef.value.select?.();
		}
	});
};

// Additive Somoni chips (+5, +10, etc.)
const addBanknote = (note) => {
	const current = currentCashAmount.value;
	const next = current + note;
	if (cashPayment.value) {
		emit("update-amount", cashPayment.value, next);
	}
	cashTextEntry.value = String(next);
};

// Bank input in split mode
const onBankInputDirect = (val) => {
	const num = Number(String(val).replace(/\s/g, "").replace(",", ".")) || 0;
	if (bankPayment.value) {
		emit("update-amount", bankPayment.value, Math.max(num, 0));
	}
};

const fillRemainderCash = () => {
	const needed = Math.max(props.payable - currentBankAmount.value, 0);
	if (cashPayment.value) {
		emit("update-amount", cashPayment.value, needed);
	}
};

const fillRemainderBank = () => {
	const needed = Math.max(props.payable - currentCashAmount.value, 0);
	if (bankPayment.value) {
		emit("update-amount", bankPayment.value, needed);
	}
};

// Initialize mode on mount or doc load
onMounted(() => {
	ensureBankLineExists();

	const hasCash = currentCashAmount.value > 0;
	const hasBank = currentBankAmount.value > 0;

	if (hasCash && hasBank) {
		activeMode.value = "split";
	} else if (hasBank && !hasCash) {
		activeMode.value = "bank";
	} else {
		activeMode.value = "cash";
	}
});

defineExpose({
	setExactCash,
	clearCashAmount,
	addBanknote,
	cashPayment,
	focusCashInput: () => cashInputRef.value?.focus?.(),
});
</script>

<style scoped>
.unified-checkout-flow {
	display: flex;
	flex-direction: column;
	gap: var(--pos-space-3, 12px);
}

/* 1. Mode Pills Bar */
.mode-pills-bar {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 8px;
	padding: 4px;
	background: var(--pos-surface-sunken, rgba(0, 0, 0, 0.05));
	border-radius: var(--pos-radius-md, 12px);
}

.mode-pill {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 8px;
	padding: 10px 14px;
	border: 1px solid transparent;
	border-radius: var(--pos-radius-sm, 8px);
	background: transparent;
	color: var(--pos-text-secondary);
	font-size: 0.95rem;
	font-weight: 700;
	cursor: pointer;
	transition: all 0.16s ease;
	outline: none;
}

.mode-pill:hover {
	color: var(--pos-text-primary);
	background: var(--pos-surface-raised, #ffffff);
}

.mode-pill--active {
	background: var(--pos-surface-raised, #ffffff) !important;
	color: rgb(var(--v-theme-primary, 11, 92, 171)) !important;
	border-color: rgba(var(--v-theme-primary, 11, 92, 171), 0.25);
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.mode-pill__icon {
	font-size: 1.15rem;
}

/* 2. Pay Cards */
.pay-card {
	background: var(--pos-surface-raised, #ffffff);
	border: 1px solid var(--pos-border-light, rgba(0, 0, 0, 0.08));
	border-radius: var(--pos-radius-md, 12px);
	padding: 16px;
	display: flex;
	flex-direction: column;
	gap: 14px;
}

/* Cash Field Wrap */
.cash-field-wrap {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.cash-field-label {
	font-size: 0.78rem;
	font-weight: 800;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
}

.cash-input-box {
	display: flex;
	align-items: center;
	background: var(--pos-surface-sunken, #f8fafc);
	border: 2px solid var(--pos-border, #cbd5e1);
	border-radius: var(--pos-radius-sm, 10px);
	padding: 4px 12px;
	gap: 8px;
	transition: border-color 0.18s ease;
}

.cash-input-box:focus-within {
	border-color: rgb(var(--v-theme-primary, 11, 92, 171));
	box-shadow: 0 0 0 3px rgba(var(--v-theme-primary, 11, 92, 171), 0.15);
}

.cash-input-box--sm {
	padding: 2px 10px;
}

.cash-input {
	flex: 1;
	font-size: 1.6rem;
	font-weight: 800;
	color: var(--pos-text-primary);
	background: transparent;
	border: 0;
	outline: none;
	width: 100%;
}

.cash-input-box--sm .cash-input {
	font-size: 1.25rem;
}

.cash-currency {
	font-size: 1.1rem;
	font-weight: 700;
	color: var(--pos-text-secondary);
}

.cash-btn-clear {
	background: transparent;
	border: 0;
	color: var(--pos-text-secondary);
	font-size: 1.1rem;
	cursor: pointer;
	padding: 4px 8px;
	border-radius: 4px;
}

.cash-btn-clear:hover {
	color: rgb(var(--v-theme-error));
	background: rgba(var(--v-theme-error), 0.1);
}

.cash-btn-exact {
	background: rgba(var(--v-theme-primary, 11, 92, 171), 0.1);
	color: rgb(var(--v-theme-primary, 11, 92, 171));
	border: 1px solid rgba(var(--v-theme-primary, 11, 92, 171), 0.3);
	font-size: 0.88rem;
	font-weight: 700;
	border-radius: 6px;
	padding: 6px 12px;
	cursor: pointer;
	white-space: nowrap;
	transition: all 0.15s ease;
}

.cash-btn-exact:hover {
	background: rgb(var(--v-theme-primary, 11, 92, 171));
	color: #ffffff;
}

/* Change Badges */
.change-status-row {
	display: flex;
	align-items: center;
}

.change-badge {
	display: inline-flex;
	align-items: center;
	gap: 10px;
	padding: 10px 14px;
	border-radius: 8px;
	font-size: 1rem;
	font-weight: 700;
	width: 100%;
}

.change-badge--give {
	background: rgba(16, 185, 129, 0.12);
	color: #047857;
	border: 1px solid rgba(16, 185, 129, 0.3);
}

.change-badge--give .change-badge__val {
	font-size: 1.45rem;
	color: #065f46;
}

.change-badge--exact {
	background: rgba(14, 165, 233, 0.1);
	color: #0284c7;
	font-size: 0.95rem;
}

.change-badge--due {
	background: rgba(245, 158, 11, 0.12);
	color: #b45309;
	border: 1px solid rgba(245, 158, 11, 0.3);
}

.change-badge--due .change-badge__val {
	font-size: 1.25rem;
	color: #92400e;
}

/* Somoni Banknotes */
.banknotes-section {
	display: flex;
	flex-direction: column;
	gap: 8px;
	margin-top: 4px;
}

.banknotes-title {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	font-size: 0.82rem;
	font-weight: 700;
	color: var(--pos-text-secondary);
}

.banknotes-hint {
	font-size: 0.74rem;
	font-weight: 500;
	color: var(--pos-text-tertiary, #94a3b8);
}

.banknotes-grid {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
}

.banknotes-grid--compact {
	gap: 6px;
	margin-top: 4px;
}

.chip-banknote {
	flex: 1 1 calc(25% - 8px);
	min-width: 68px;
	padding: 8px 10px;
	background: var(--pos-surface-raised, #ffffff);
	border: 1.5px solid var(--pos-border, #e2e8f0);
	border-radius: 8px;
	font-size: 1rem;
	font-weight: 800;
	color: var(--pos-text-primary);
	cursor: pointer;
	text-align: center;
	transition: all 0.15s ease;
	outline: none;
}

.chip-banknote:hover {
	border-color: rgb(var(--v-theme-primary, 11, 92, 171));
	color: rgb(var(--v-theme-primary, 11, 92, 171));
	background: rgba(var(--v-theme-primary, 11, 92, 171), 0.05);
	transform: translateY(-1px);
}

.chip-banknote:active {
	transform: translateY(0);
}

.chip-banknote--exact {
	background: rgba(var(--v-theme-primary, 11, 92, 171), 0.12);
	color: rgb(var(--v-theme-primary, 11, 92, 171));
	border-color: rgba(var(--v-theme-primary, 11, 92, 171), 0.35);
}

.chip-banknote--sm {
	padding: 5px 8px;
	font-size: 0.88rem;
	min-width: 52px;
}

/* Bank Mode */
.bank-header-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 12px 14px;
	background: rgba(var(--v-theme-primary, 11, 92, 171), 0.06);
	border-radius: 8px;
	border: 1px solid rgba(var(--v-theme-primary, 11, 92, 171), 0.18);
}

.bank-target-total {
	display: flex;
	flex-direction: column;
}

.bank-target-total__label {
	font-size: 0.82rem;
	font-weight: 600;
	color: var(--pos-text-secondary);
}

.bank-target-total__val {
	font-size: 1.5rem;
	font-weight: 800;
	color: rgb(var(--v-theme-primary, 11, 92, 171));
}

.bank-no-change-badge {
	font-size: 0.84rem;
	font-weight: 700;
	color: #047857;
}

.bank-picker-section {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.bank-picker-label {
	font-size: 0.82rem;
	font-weight: 700;
	color: var(--pos-text-secondary);
}

.bank-grid {
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	gap: 8px;
}

.bank-grid--compact {
	grid-template-columns: repeat(2, 1fr);
	gap: 6px;
	margin-top: 4px;
}

.bank-chip {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 12px 14px;
	border: 1.5px solid var(--pos-border, #e2e8f0);
	border-radius: 8px;
	background: var(--pos-surface-raised, #ffffff);
	cursor: pointer;
	transition: all 0.16s ease;
	outline: none;
}

.bank-chip:hover {
	border-color: var(--bank-brand-color, #0b5cab);
	background: rgba(0, 0, 0, 0.02);
}

.bank-chip--active {
	border-color: var(--bank-brand-color, #0b5cab) !important;
	background: rgba(0, 0, 0, 0.03) !important;
	box-shadow: 0 0 0 2px var(--bank-brand-color, #0b5cab);
}

.bank-chip__indicator {
	width: 12px;
	height: 12px;
	border-radius: 50%;
	flex-shrink: 0;
}

.bank-chip__name {
	flex: 1;
	text-align: left;
	font-size: 0.92rem;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.bank-chip__check {
	color: var(--bank-brand-color, #0b5cab);
	font-weight: 800;
}

.bank-chip--sm {
	padding: 6px 10px;
}

.bank-chip--sm .bank-chip__name {
	font-size: 0.82rem;
}

.bank-info-note {
	display: flex;
	align-items: center;
	font-size: 0.82rem;
	color: var(--pos-text-secondary);
	padding: 8px 12px;
	border-radius: 6px;
	background: var(--pos-surface-sunken, #f8fafc);
}

/* Split Mode */
.split-rows {
	display: flex;
	flex-direction: column;
	gap: 14px;
}

.split-line {
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 10px;
	border-radius: 8px;
	background: var(--pos-surface-sunken, #f8fafc);
	border: 1px solid var(--pos-border-light, #e2e8f0);
}

.split-line__header {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.split-line__title {
	font-size: 0.88rem;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.split-btn-fill {
	border: 0;
	background: rgba(var(--v-theme-primary, 11, 92, 171), 0.12);
	color: rgb(var(--v-theme-primary, 11, 92, 171));
	font-size: 0.75rem;
	font-weight: 700;
	padding: 3px 8px;
	border-radius: 999px;
	cursor: pointer;
}

.split-btn-fill:hover {
	background: rgb(var(--v-theme-primary, 11, 92, 171));
	color: #ffffff;
}

.split-summary-bar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 10px 14px;
	border-radius: 8px;
	background: var(--pos-surface-sunken, #f8fafc);
	border: 1px solid var(--pos-border-light, #e2e8f0);
	font-size: 0.92rem;
}

.split-summary-item strong {
	margin-left: 6px;
}

.split-summary-item--change {
	color: #047857;
	font-weight: 700;
}

.split-summary-item--due {
	color: #b45309;
	font-weight: 700;
}

.split-summary-item--ok {
	color: #047857;
	font-weight: 700;
}

@media (max-width: 600px) {
	.mode-pills-bar {
		grid-template-columns: 1fr;
	}
	.bank-grid {
		grid-template-columns: 1fr;
	}
	.chip-banknote {
		flex: 1 1 calc(33.3% - 8px);
	}
}
</style>
