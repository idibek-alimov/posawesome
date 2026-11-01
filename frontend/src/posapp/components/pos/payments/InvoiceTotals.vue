<template>
	<div v-if="invoice_doc" class="checkout-totals-panel">
		<!-- 1. The Core Equation: Сумма покупки − Скидка [− Баллы] = К оплате -->
		<div
			class="eq-equation-board"
			:class="{ 'eq-equation-board--with-loyalty': loyaltyAmount > 0 }"
		>
			<!-- A. Сумма покупки (Non-editable) -->
			<div class="eq-step eq-step--subtotal">
				<div class="eq-step__header">
					<span class="eq-step__label">{{ frappe._("Сумма покупки") }}</span>
				</div>
				<div class="eq-step__display">
					<span class="eq-step__number">{{ formatCurrency(subtotal) }}</span>
					<span class="eq-step__currency">{{ displayCurrency }}</span>
				</div>
				<div class="eq-step__hint">
					{{ frappe._("Сумма позиций") }}
				</div>
			</div>

			<!-- Operator: Minus -->
			<div class="eq-operator eq-operator--minus" aria-hidden="true">
				<span>−</span>
			</div>

			<!-- B. Скидка (Flat amount input + % button + Big/Small font display) -->
			<div
				class="eq-step eq-step--discount"
				:class="{ 'eq-step--locked': discountLocked, 'eq-step--has-discount': discountAmount > 0 }"
				@click="discountLocked ? onDiscountLockedClick() : null"
			>
				<div class="eq-step__header">
					<span class="eq-step__label">
						<v-icon
							:icon="discountLocked ? 'mdi-shield-lock-outline' : 'mdi-shield-check-outline'"
							:color="discountLocked ? 'warning' : 'success'"
							size="16"
							class="mr-1"
						/>
						{{ frappe._("Скидка") }}
					</span>
					<v-chip
						v-if="discountPercent > 0"
						size="x-small"
						color="error"
						variant="flat"
						class="font-weight-bold eq-percent-chip"
					>
						−{{ formatPercent(discountPercent) }}%
					</v-chip>
				</div>

				<div class="eq-step__display eq-step__display--discount">
					<span class="eq-step__number text-error">
						{{ discountAmount > 0 ? '−' + formatCurrency(discountAmount) : '0.00' }}
					</span>
					<span class="eq-step__currency text-error">{{ displayCurrency }}</span>
				</div>

				<!-- Discount inputs: Flat amount + % button -->
				<div v-if="!isReturn" class="eq-discount-actions" @click.stop>
					<div class="eq-input-row">
						<v-text-field
							density="compact"
							variant="solo"
							hide-details
							class="sleek-field pos-themed-input eq-amount-input"
							:placeholder="frappe._('Сумма')"
							:model-value="amountInput"
							:prefix="currencySymbol(invoice_doc.currency)"
							inputmode="decimal"
							:readonly="discountLocked"
							:tabindex="discountLocked ? -1 : 0"
							@click="discountLocked ? onDiscountLockedClick() : null"
							@update:model-value="onAmountInput"
						/>

						<!-- Clickable % button with quick presets menu -->
						<v-menu
							v-model="percentMenuOpen"
							:close-on-content-click="false"
							location="bottom end"
							:disabled="discountLocked"
						>
							<template #activator="{ props: menuProps }">
								<v-btn
									v-bind="menuProps"
									color="primary"
									variant="tonal"
									class="eq-percent-btn font-weight-bold"
									:disabled="discountLocked"
									:title="frappe._('Задать скидку в процентах (%)')"
									@click="discountLocked ? onDiscountLockedClick() : null"
								>
									%
								</v-btn>
							</template>

							<v-card class="percent-presets-card pa-3 elevation-8" min-width="260">
								<div class="text-caption font-weight-bold text-grey-darken-2 mb-2">
									{{ frappe._("Скидка в процентах (%)") }}
								</div>

								<!-- Quick Presets -->
								<div class="percent-presets-grid mb-3">
									<v-btn
										v-for="p in [5, 10, 15, 20, 25, 50]"
										:key="p"
										size="small"
										variant="outlined"
										color="primary"
										class="font-weight-bold"
										@click="applyPercentPreset(p)"
									>
										{{ p }}%
									</v-btn>
								</div>

								<!-- Custom Percent Input -->
								<div class="d-flex align-center gap-2">
									<v-text-field
										v-model="customPercentDraft"
										density="compact"
										variant="outlined"
										hide-details
										suffix="%"
										type="number"
										min="0"
										max="100"
										placeholder="0"
										class="custom-percent-input"
										@keydown.enter="applyCustomPercent"
									/>
									<v-btn
										color="primary"
										size="small"
										variant="flat"
										class="ml-2 font-weight-bold"
										@click="applyCustomPercent"
									>
										{{ frappe._("OK") }}
									</v-btn>
								</div>
							</v-card>
						</v-menu>
					</div>

					<div v-if="discountLocked" class="eq-lock-banner" @click="onDiscountLockedClick">
						<span>🔒 {{ frappe._("Нажмите для авторизации администратора") }}</span>
					</div>
				</div>
			</div>

			<!-- Optional Operator & Step: Minus Loyalty (Appears whenever loyalty is spent!) -->
			<template v-if="loyaltyAmount > 0">
				<div class="eq-operator eq-operator--minus" aria-hidden="true">
					<span>−</span>
				</div>

				<div class="eq-step eq-step--loyalty">
					<div class="eq-step__header">
						<span class="eq-step__label text-amber-darken-3 font-weight-bold">
							⭐ {{ frappe._("Баллы") }}
						</span>
					</div>
					<div class="eq-step__display eq-step__display--loyalty">
						<span class="eq-step__number text-amber-darken-3">
							{{ formatCurrency(loyaltyAmount) }}
						</span>
						<span class="eq-step__currency text-amber-darken-3">{{ displayCurrency }}</span>
					</div>
					<div class="eq-step__hint">
						{{ frappe._("Оплата баллами") }}
					</div>
				</div>
			</template>

			<!-- Operator: Equals -->
			<div class="eq-operator eq-operator--equals" aria-hidden="true">
				<span>=</span>
			</div>

			<!-- C. К оплате (Editable net total) -->
			<div
				class="eq-step eq-step--payable"
				:class="{ 'eq-step--locked': discountLocked }"
				@click="discountLocked ? onDiscountLockedClick() : null"
			>
				<div class="eq-step__header">
					<span class="eq-step__label font-weight-bold">
						{{ isReturn ? frappe._("К возврату") : (loyaltyAmount > 0 ? frappe._("К оплате деньгами") : frappe._("К оплате")) }}
					</span>
				</div>

				<div v-if="isReturn" class="eq-step__display eq-step__display--payable">
					<span class="eq-step__number">{{ formatCurrency(Math.abs(payable)) }}</span>
					<span class="eq-step__currency">{{ displayCurrency }}</span>
				</div>

				<div v-else class="eq-net-editor" @click.stop>
					<div class="eq-net-input-wrap">
						<input
							class="eq-net-input"
							inputmode="decimal"
							:value="netEditing ? netInput : formatNet(payable)"
							:readonly="discountLocked"
							:tabindex="discountLocked ? -1 : 0"
							:title="frappe._('Договорная сумма: введите итог, скидка рассчитается автоматически')"
							@click="discountLocked ? onDiscountLockedClick() : null"
							@focus="onNetFocus"
							@input="onNetInput($event.target.value)"
							@blur="onNetBlur"
							@keydown.enter.stop="$event.target.blur()"
						/>
						<span class="eq-step__currency text-primary">{{ displayCurrency }}</span>
					</div>
					<div class="eq-step__hint">
						{{ loyaltyAmount > 0 ? frappe._("Наличными или картой") : frappe._("Договорной итог (скидка пересчитается)") }}
					</div>
				</div>
			</div>
		</div>

		<!-- 2. Loyalty Points Card (Prominent & Clear) -->
		<div v-if="showLoyalty" class="loyalty-card" :class="{ 'loyalty-card--active': hasLoyaltyProgram }">
			<!-- Customer Identity Header -->
			<div class="loyalty-customer-info">
				<div class="d-flex align-center gap-2">
					<div class="customer-avatar-icon">
						<v-icon icon="mdi-account" size="16" color="primary" />
					</div>
					<div class="d-flex align-center gap-2 flex-wrap">
						<span class="customer-name-text">{{ customerName }}</span>
						<div v-if="customerPhone" class="customer-phone-badge">
							<v-icon icon="mdi-phone" size="13" class="mr-1 text-grey-darken-1" />
							<span class="customer-phone-text">{{ customerPhone }}</span>
						</div>
					</div>
				</div>
				<v-chip
					v-if="hasLoyaltyProgram"
					size="small"
					color="amber-darken-3"
					variant="flat"
					class="font-weight-bold loyalty-program-chip"
				>
					{{ customerInfo.loyalty_program }}
				</v-chip>
			</div>

			<div class="loyalty-head">
				<div class="d-flex align-center gap-2">
					<span class="loyalty-title">⭐ {{ frappe._("Баллы клиента") }}</span>
				</div>
				<div class="loyalty-balance" v-if="hasLoyaltyProgram">
					<span class="loyalty-balance__label">{{ frappe._("Доступно") }}:</span>
					<strong class="loyalty-balance__pts">{{ formatPoints(customerPoints) }}</strong>
					<span class="loyalty-balance__unit">{{ frappe._("баллов") }}</span>
					<span v-if="availablePointsAmount > 0" class="loyalty-balance__eq">
						(= {{ money(availablePointsAmount) }})
					</span>
				</div>
			</div>

			<!-- Redeem field if customer has available points -->
			<div v-if="hasLoyaltyProgram && availablePointsAmount > 0" class="loyalty-action-row">
				<v-text-field
					density="compact"
					variant="solo"
					hide-details
					class="sleek-field pos-themed-input flex-grow-1 loyalty-redeem-input"
					:label="frappe._('Списать баллами сейчас')"
					:model-value="loyaltyInput"
					:prefix="currencySymbol(invoice_doc.currency)"
					inputmode="decimal"
					@update:model-value="onLoyaltyInput"
				/>
				<button type="button" class="loyalty-max-btn" @click="useMaxPoints">
					{{ frappe._("Списать максимум") }}
				</button>
			</div>

			<!-- Live summary pill when loyalty is redeemed -->
			<div v-if="hasLoyaltyProgram && loyaltyAmount > 0" class="loyalty-applied-banner">
				<span class="loyalty-applied-text">
					✓ {{ frappe._("Оплачивается баллами") }}:
					<strong>{{ formatCurrency(loyaltyAmount) }} {{ displayCurrency }}</strong>
					({{ formatPoints(loyaltyAmount) }} {{ frappe._("баллов") }})
				</span>
				<button type="button" class="loyalty-cancel-btn" @click="emit('update-loyalty', '0')">
					✕ {{ frappe._("Отменить списание") }}
				</button>
			</div>

			<!-- Points that will be earned on this purchase -->
			<div v-if="hasLoyaltyProgram && pointsToEarn !== null" class="loyalty-earn-badge">
				🎁 {{ frappe._("Начислится баллов за эту покупку") }}:
				<strong>+{{ formatPoints(pointsToEarn) }}</strong>
			</div>

			<!-- Customer without loyalty program (e.g. Гость) -->
			<div v-else-if="!hasLoyaltyProgram" class="loyalty-empty-hint">
				<v-icon icon="mdi-information-outline" size="18" class="mr-1 text-grey-darken-1" />
				<span class="loyalty-empty-hint__text">
					{{ customerName ? frappe._("Для покупателя «{0}» программа лояльности не подключена", [customerName]) : frappe._("Программа лояльности не подключена") }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useCustomersStore } from "../../../stores/customersStore";

const customersStore = useCustomersStore();

const props = defineProps({
	invoice_doc: Object,
	displayCurrency: String,
	diff_payment: Number,
	diff_label: String,
	itemDiscountTotal: { type: Number, default: 0 },
	currencySymbol: Function,
	formatCurrency: Function,
	customerInfo: { type: [Object, String], default: () => ({}) },
	availablePointsAmount: { type: Number, default: 0 },
	loyaltyAmount: { type: Number, default: 0 },
	payable: { type: Number, default: 0 },
	discountLocked: { type: Boolean, default: false },
});

const emit = defineEmits(["update-discount", "update-loyalty", "request-manager"]);

const frappe = window.frappe;

const toNumber = (value) => {
	const parsed = Number(String(value ?? "").replace(/\s/g, "").replace(",", "."));
	return Number.isFinite(parsed) ? parsed : 0;
};

const money = (v) => `${props.formatCurrency(v, props.displayCurrency)} ${props.displayCurrency || ""}`.trim();
const formatPoints = (v) => Number(v || 0).toLocaleString("ru-RU", { maximumFractionDigits: 0 });

const formatPercent = (v) => {
	const num = Number(v || 0);
	return Number.isInteger(num) ? String(num) : num.toFixed(1);
};

const isReturn = computed(() => Boolean(props.invoice_doc?.is_return));
const discountAmount = computed(() => Math.abs(toNumber(props.invoice_doc?.discount_amount)));

// Amount before the additional discount (items already include their own rate discounts)
const subtotal = computed(() => {
	const doc = props.invoice_doc || {};
	return Math.abs(toNumber(doc.grand_total)) + (isReturn.value ? 0 : discountAmount.value);
});

// Percentage of the additional discount
const discountPercent = computed(() => {
	const doc = props.invoice_doc || {};
	const explicitPct = Math.abs(toNumber(doc.additional_discount_percentage));
	if (explicitPct > 0) return explicitPct;
	const sub = subtotal.value;
	if (sub > 0 && discountAmount.value > 0) {
		return Math.min((discountAmount.value / sub) * 100, 100);
	}
	return 0;
});

// ---- discount inputs ----
const amountInput = ref("");
const percentMenuOpen = ref(false);
const customPercentDraft = ref("");

const syncDiscountInputs = () => {
	const amt = discountAmount.value;
	amountInput.value = amt > 0 ? String(amt) : "";
};
watch(
	() => [props.invoice_doc?.discount_amount, props.invoice_doc?.additional_discount_percentage],
	syncDiscountInputs,
	{ immediate: true },
);

const onDiscountLockedClick = () => {
	if (props.discountLocked) {
		emit("request-manager");
	}
};

const onAmountInput = (value) => {
	if (props.discountLocked) return;
	amountInput.value = value;
	emit("update-discount", { amount: toNumber(value), percentage: 0 });
};

const applyPercentPreset = (p) => {
	percentMenuOpen.value = false;
	const cleanPct = Math.min(Math.max(toNumber(p), 0), 100);
	emit("update-discount", { amount: 0, percentage: cleanPct });
};

const applyCustomPercent = () => {
	if (customPercentDraft.value === "") return;
	percentMenuOpen.value = false;
	const cleanPct = Math.min(Math.max(toNumber(customPercentDraft.value), 0), 100);
	customPercentDraft.value = "";
	emit("update-discount", { amount: 0, percentage: cleanPct });
};

// ---- agreed net (reverse discount) ----
const netInput = ref("");
const netEditing = ref(false);
const formatNet = (v) => props.formatCurrency(Math.max(v, 0), props.displayCurrency);

const onNetFocus = (event) => {
	if (props.discountLocked) {
		event?.target?.blur?.();
		return;
	}
	netEditing.value = true;
	netInput.value = String(Math.max(props.payable, 0));
	event?.target?.select?.();
};

const onNetInput = (value) => {
	if (props.discountLocked) return;
	netInput.value = value;
	if (String(value).trim() === "") return;
	let net = Math.max(toNumber(value), 0);
	// Net cannot exceed the amount without discount
	const maxNet = props.payable + discountAmount.value;
	if (net > maxNet) {
		net = maxNet;
		netInput.value = String(net);
		frappe.show_alert?.({
			message: frappe._("Договорная сумма не может быть больше суммы покупки"),
			indicator: "orange",
		});
	}
	const newDiscount = Math.max(discountAmount.value + (props.payable - net), 0);
	amountInput.value = newDiscount > 0 ? String(newDiscount) : "";
	emit("update-discount", { amount: newDiscount, percentage: 0 });
};

const onNetBlur = () => {
	netEditing.value = false;
};

// ---- loyalty ----
const customerName = computed(() => {
	const info = props.customerInfo || {};
	return (
		info.customer_name ||
		info.customer ||
		info.name ||
		props.invoice_doc?.customer_name ||
		props.invoice_doc?.customer ||
		customersStore.selectedCustomer?.customer_name ||
		customersStore.selectedCustomer?.name ||
		frappe._("Гость")
	);
});

const customerPhone = computed(() => {
	const info = props.customerInfo || {};
	return (
		info.mobile_no ||
		props.invoice_doc?.contact_mobile ||
		props.invoice_doc?.mobile_no ||
		customersStore.selectedCustomer?.mobile_no ||
		customersStore.customerInfo?.mobile_no ||
		""
	);
});
const hasLoyaltyProgram = computed(() => Boolean(props.customerInfo?.loyalty_program));
const customerPoints = computed(() => toNumber(props.customerInfo?.loyalty_points));
const showLoyalty = computed(() => !isReturn.value);
const loyaltyInput = ref("");
watch(
	() => props.loyaltyAmount,
	(v) => {
		const n = toNumber(v);
		if (n !== toNumber(loyaltyInput.value)) loyaltyInput.value = n > 0 ? String(n) : "";
	},
	{ immediate: true },
);
const onLoyaltyInput = (value) => {
	loyaltyInput.value = value;
	emit("update-loyalty", String(toNumber(value)));
};
const useMaxPoints = () => {
	const cap = Math.min(props.availablePointsAmount, Math.max(props.payable + toNumber(props.loyaltyAmount), 0));
	loyaltyInput.value = String(cap);
	emit("update-loyalty", String(cap));
};

// ---- points to earn ----
const pointsToEarn = computed(() => {
	const factor = toNumber(props.customerInfo?.collection_factor);
	if (!props.customerInfo?.loyalty_program || factor <= 0) return null;
	return Math.max(Math.floor(Math.max(props.payable, 0) / factor), 0);
});
</script>

<style scoped>
.checkout-totals-panel {
	display: flex;
	flex-direction: column;
	gap: 12px;
}

/* 1. Equation Board */
.eq-equation-board {
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto minmax(0, 1.25fr) auto minmax(0, 1.15fr);
	gap: 8px;
	align-items: center;
	padding: 12px;
	background: var(--pos-surface-muted, #f8fafc);
	border: 1px solid var(--pos-border-light, #e2e8f0);
	border-radius: var(--pos-radius-lg, 14px);
}

.eq-equation-board--with-loyalty {
	grid-template-columns: minmax(0, 1fr) auto minmax(0, 1.15fr) auto minmax(0, 0.95fr) auto minmax(0, 1.15fr);
}

.eq-step {
	display: flex;
	flex-direction: column;
	gap: 4px;
	padding: 10px 12px;
	background: #ffffff;
	border: 1px solid var(--pos-border-light, #e2e8f0);
	border-radius: var(--pos-radius-md, 10px);
	min-width: 0;
	transition: all 0.2s ease;
}

.eq-step__header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	min-height: 22px;
}

.eq-step__label {
	font-size: 0.78rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	color: var(--pos-text-secondary, #64748b);
	display: inline-flex;
	align-items: center;
}

.eq-step__display {
	display: flex;
	align-items: baseline;
	gap: 4px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.eq-step__number {
	font-size: 1.55rem;
	font-weight: 800;
	line-height: 1.15;
	color: var(--pos-text-primary, #0f172a);
	letter-spacing: -0.02em;
}

.eq-step__currency {
	font-size: 0.95rem;
	font-weight: 700;
	color: var(--pos-text-secondary, #64748b);
}

.eq-step__hint {
	font-size: 0.72rem;
	color: var(--pos-text-muted, #94a3b8);
	font-weight: 500;
}

/* Operators (− and =) */
.eq-operator {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 26px;
	height: 26px;
	border-radius: 999px;
	background: #e2e8f0;
	color: #475569;
	font-size: 1.2rem;
	font-weight: 900;
	line-height: 1;
	user-select: none;
}

.eq-operator--minus {
	background: #fee2e2;
	color: #ef4444;
}

.eq-operator--equals {
	background: #dbeafe;
	color: #2563eb;
}

/* Discount Specific */
.eq-step--discount {
	border-color: #fecaca;
	background: #fffafa;
}

.eq-step--discount.eq-step--locked {
	cursor: pointer;
}

.eq-step--discount.eq-step--locked:hover {
	border-color: #fca5a5;
	box-shadow: 0 2px 8px rgba(239, 68, 68, 0.08);
}

.eq-percent-chip {
	font-size: 0.75rem !important;
	height: 20px !important;
}

.eq-discount-actions {
	margin-top: 4px;
	display: flex;
	flex-direction: column;
	gap: 4px;
}

.eq-input-row {
	display: flex;
	align-items: center;
	gap: 6px;
}

.eq-amount-input {
	flex: 1 1 auto;
	min-width: 0;
}

.eq-percent-btn {
	min-width: 36px !important;
	width: 36px !important;
	height: 36px !important;
	padding: 0 !important;
	border-radius: 8px !important;
	font-size: 1rem !important;
}

.eq-lock-banner {
	font-size: 0.72rem;
	font-weight: 600;
	color: #b45309;
	background: #fef3c7;
	padding: 3px 6px;
	border-radius: 6px;
	cursor: pointer;
	text-align: center;
	transition: background 0.15s ease;
}

.eq-lock-banner:hover {
	background: #fde68a;
}

/* Loyalty Step in Equation */
.eq-step--loyalty {
	border-color: #fde68a !important;
	background: #fffdf5 !important;
}

.eq-step__display--loyalty .eq-step__number {
	color: #d97706 !important;
}

/* Percent presets popover */
.percent-presets-card {
	border-radius: 12px;
}

.percent-presets-grid {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 6px;
}

/* Payable Step */
.eq-step--payable {
	border-color: #bfdbfe;
	background: #f8fbff;
}

.eq-step--payable.eq-step--locked {
	cursor: pointer;
}

.eq-net-editor {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.eq-net-input-wrap {
	display: flex;
	align-items: baseline;
	gap: 6px;
}

.eq-net-input {
	width: 100%;
	font-size: 1.55rem;
	font-weight: 800;
	line-height: 1.15;
	color: #0284c7;
	background: transparent;
	border: 0;
	border-bottom: 2px dashed rgba(2, 132, 199, 0.4);
	outline: none;
	padding: 0;
	transition: border-color 0.2s;
}

.eq-net-input:focus {
	border-bottom: 2px solid #0284c7;
}

/* 2. Loyalty Card (Enlarged, Clear & Modern) */
.loyalty-card {
	display: flex;
	flex-direction: column;
	gap: 12px;
	padding: 16px 18px;
	border-radius: var(--pos-radius-lg, 14px);
	background: linear-gradient(135deg, #fffdf7 0%, #ffffff 100%);
	border: 1.5px solid #fde68a;
	box-shadow: 0 2px 8px rgba(217, 119, 6, 0.05);
}

.loyalty-customer-info {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding-bottom: 10px;
	border-bottom: 1px solid rgba(245, 158, 11, 0.2);
}

.customer-avatar-icon {
	width: 28px;
	height: 28px;
	border-radius: 50%;
	background: #eff6ff;
	border: 1px solid #bfdbfe;
	display: flex;
	align-items: center;
	justify-content: center;
}

.customer-name-text {
	font-size: 0.95rem;
	font-weight: 700;
	color: #0f172a;
}

.customer-phone-badge {
	display: inline-flex;
	align-items: center;
	padding: 2px 8px;
	background: #ffffff;
	border: 1px solid #e2e8f0;
	border-radius: 6px;
	font-size: 0.8rem;
	color: #475569;
	font-weight: 600;
}

.loyalty-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	flex-wrap: wrap;
	gap: 8px;
}

.loyalty-title {
	font-size: 1.15rem;
	font-weight: 800;
	color: var(--pos-text-primary, #0f172a);
	letter-spacing: -0.01em;
}

.loyalty-program-chip {
	font-size: 0.82rem !important;
	font-weight: 700 !important;
}

.loyalty-balance {
	display: flex;
	align-items: baseline;
	gap: 6px;
	font-size: 1.05rem;
	color: var(--pos-text-secondary, #475569);
}

.loyalty-balance__label {
	font-size: 0.9rem;
	color: #64748b;
}

.loyalty-balance__pts {
	color: #d97706;
	font-size: 1.35rem;
	font-weight: 800;
	font-variant-numeric: tabular-nums;
}

.loyalty-balance__unit {
	font-weight: 600;
	color: #475569;
}

.loyalty-balance__eq {
	font-size: 1rem;
	font-weight: 700;
	color: #b45309;
}

.loyalty-action-row {
	display: flex;
	align-items: center;
	gap: 10px;
}

.loyalty-redeem-input :deep(.v-field__input),
.loyalty-redeem-input :deep(input) {
	font-size: 1.25rem !important;
	font-weight: 700 !important;
	color: #b45309 !important;
}

.loyalty-redeem-input :deep(.v-label) {
	font-size: 0.95rem !important;
	font-weight: 600 !important;
}

.loyalty-max-btn {
	height: 40px;
	padding: 0 16px;
	border: 0;
	border-radius: 8px;
	font-size: 0.88rem;
	font-weight: 700;
	cursor: pointer;
	color: #ffffff;
	background: #d97706;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	white-space: nowrap;
	flex-shrink: 0;
	transition: all 0.2s ease;
	box-shadow: 0 2px 6px rgba(217, 119, 6, 0.25);
}

.loyalty-max-btn:hover {
	background: #b45309;
	box-shadow: 0 4px 10px rgba(217, 119, 6, 0.35);
	transform: translateY(-1px);
}

.loyalty-applied-banner {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 8px 12px;
	background: #ecfdf5;
	border: 1px solid #a7f3d0;
	border-radius: 8px;
}

.loyalty-applied-text {
	font-size: 0.95rem;
	color: #065f46;
}

.loyalty-applied-text strong {
	font-size: 1.05rem;
	font-weight: 800;
	color: #047857;
}

.loyalty-cancel-btn {
	background: transparent;
	border: 0;
	font-size: 0.82rem;
	font-weight: 700;
	color: #dc2626;
	cursor: pointer;
	padding: 2px 6px;
	border-radius: 4px;
}

.loyalty-cancel-btn:hover {
	background: rgba(220, 38, 38, 0.08);
}

.loyalty-earn-badge {
	font-size: 0.95rem;
	color: #475569;
	text-align: right;
	font-weight: 600;
}

.loyalty-earn-badge strong {
	color: #16a34a;
	font-size: 1.2rem;
	font-weight: 800;
}

.loyalty-empty-hint {
	display: flex;
	align-items: center;
	padding: 6px 0;
}

.loyalty-empty-hint__text {
	font-size: 0.88rem;
	color: #64748b;
}

@media (max-width: 900px) {
	.eq-equation-board,
	.eq-equation-board--with-loyalty {
		grid-template-columns: 1fr;
		gap: 10px;
	}
	.eq-operator {
		margin: 0 auto;
	}
}
</style>
