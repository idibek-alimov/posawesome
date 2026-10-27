<template>
	<div v-if="invoice_doc" class="checkout-totals">
		<!-- 1. Order amount -->
		<div class="ct-row">
			<span class="ct-label">{{ frappe._("Сумма покупки") }}</span>
			<span class="ct-value">{{ money(subtotal) }}</span>
		</div>

		<!-- 2. Additional (admin) discount -->
		<div v-if="!isReturn" class="ct-block">
			<div class="ct-block-head">
				<span class="ct-label">
					<v-icon :icon="discountLocked ? 'mdi-lock-outline' : 'mdi-lock-open-variant-outline'" size="16" />
					{{ frappe._("Скидка (администратор)") }}
				</span>
				<span class="ct-value ct-value--minus" v-if="discountAmount > 0">−{{ money(discountAmount) }}</span>
			</div>
			<div class="ct-inputs">
				<v-text-field
					density="compact"
					variant="solo"
					hide-details
					class="sleek-field pos-themed-input"
					:label="frappe._('Сумма скидки')"
					:model-value="amountInput"
					:prefix="currencySymbol(invoice_doc.currency)"
					inputmode="decimal"
					:readonly="discountLocked"
					@focus="onDiscountFocus"
					@update:model-value="onAmountInput"
				/>
				<v-text-field
					density="compact"
					variant="solo"
					hide-details
					class="sleek-field pos-themed-input"
					:label="frappe._('Скидка, %')"
					:model-value="percentInput"
					suffix="%"
					inputmode="decimal"
					:readonly="discountLocked"
					@focus="onDiscountFocus"
					@update:model-value="onPercentInput"
				/>
			</div>
			<div v-if="discountLocked" class="ct-hint">
				{{ frappe._("Отсканируйте штрихкод администратора, чтобы дать скидку") }}
			</div>
		</div>

		<!-- 3. Loyalty points -->
		<div v-if="showLoyalty" class="ct-block">
			<div class="ct-block-head">
				<span class="ct-label">⭐ {{ frappe._("Баллы клиента") }}</span>
				<span class="ct-value">
					{{ formatPoints(customerPoints) }} {{ frappe._("баллов") }}
					<small v-if="availablePointsAmount > 0">(= {{ money(availablePointsAmount) }})</small>
				</span>
			</div>
			<v-text-field
				v-if="availablePointsAmount > 0"
				density="compact"
				variant="solo"
				hide-details
				class="sleek-field pos-themed-input"
				:label="frappe._('Списать баллами сейчас')"
				:model-value="loyaltyInput"
				:prefix="currencySymbol(invoice_doc.currency)"
				inputmode="decimal"
				@update:model-value="onLoyaltyInput"
			>
				<template #append-inner>
					<button type="button" class="ct-chip" @click="useMaxPoints">
						{{ frappe._("Макс") }}
					</button>
				</template>
			</v-text-field>
		</div>

		<!-- 4. Amount to pay -->
		<div class="ct-total">
			<span>{{ isReturn ? frappe._("К возврату") : frappe._("К оплате") }}</span>
			<strong>{{ money(Math.abs(payable)) }}</strong>
		</div>

		<!-- 5. Points that will be earned -->
		<div v-if="pointsToEarn !== null && !isReturn" class="ct-earn">
			🎁 {{ frappe._("Начислится баллов за эту покупку") }}:
			<strong>+{{ formatPoints(pointsToEarn) }}</strong>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

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

const isReturn = computed(() => Boolean(props.invoice_doc?.is_return));
const discountAmount = computed(() => Math.abs(toNumber(props.invoice_doc?.discount_amount)));

// Amount before the additional discount (items already include their own rate discounts)
const subtotal = computed(() => {
	const doc = props.invoice_doc || {};
	return Math.abs(toNumber(doc.grand_total)) + (isReturn.value ? 0 : discountAmount.value);
});

// ---- discount inputs ----
const amountInput = ref("");
const percentInput = ref("");
const syncDiscountInputs = () => {
	const doc = props.invoice_doc || {};
	const pct = Math.abs(toNumber(doc.additional_discount_percentage));
	const amt = discountAmount.value;
	amountInput.value = pct > 0 ? "" : amt > 0 ? String(amt) : "";
	percentInput.value = pct > 0 ? String(pct) : "";
};
watch(
	() => [props.invoice_doc?.discount_amount, props.invoice_doc?.additional_discount_percentage],
	syncDiscountInputs,
	{ immediate: true },
);

const onDiscountFocus = (event) => {
	if (props.discountLocked) {
		event?.target?.blur?.();
		emit("request-manager");
	}
};
const onAmountInput = (value) => {
	if (props.discountLocked) return;
	amountInput.value = value;
	percentInput.value = "";
	emit("update-discount", { amount: toNumber(value), percentage: 0 });
};
const onPercentInput = (value) => {
	if (props.discountLocked) return;
	percentInput.value = value;
	amountInput.value = "";
	emit("update-discount", { amount: 0, percentage: toNumber(value) });
};

// ---- loyalty ----
const customerPoints = computed(() => toNumber(props.customerInfo?.loyalty_points));
const showLoyalty = computed(() => !isReturn.value && customerPoints.value > 0);
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
.checkout-totals {
	display: flex;
	flex-direction: column;
	gap: var(--pos-space-2, 8px);
}

.ct-row,
.ct-block-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
}

.ct-label {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	font-size: 0.9rem;
	font-weight: 600;
	color: var(--pos-text-secondary);
}

.ct-value {
	font-weight: 700;
	color: var(--pos-text-primary);
}

.ct-value small {
	font-weight: 500;
	color: var(--pos-text-secondary);
}

.ct-value--minus {
	color: rgb(var(--v-theme-error));
}

.ct-block {
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 10px 12px;
	border-radius: var(--pos-radius-sm, 8px);
	background: var(--pos-surface-raised);
}

.ct-inputs {
	display: grid;
	grid-template-columns: 3fr 2fr;
	gap: 8px;
}

.ct-hint {
	font-size: 0.78rem;
	color: rgb(var(--v-theme-warning));
}

.ct-chip {
	border: 0;
	padding: 2px 10px;
	border-radius: 999px;
	font-size: 0.75rem;
	font-weight: 700;
	cursor: pointer;
	color: rgb(var(--v-theme-primary));
	background: rgba(var(--v-theme-primary), 0.12);
}

.ct-total {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	margin-top: 4px;
	padding: 14px 16px;
	border-radius: var(--pos-radius-md, 12px);
	font-size: 1.05rem;
	font-weight: 700;
	background: rgba(var(--v-theme-primary), 0.1);
	border: 1px solid rgba(var(--v-theme-primary), 0.25);
}

.ct-total strong {
	font-size: 1.6rem;
	color: rgb(var(--v-theme-primary));
}

.ct-earn {
	font-size: 0.88rem;
	color: var(--pos-text-secondary);
	text-align: right;
}

.ct-earn strong {
	color: rgb(var(--v-theme-success));
	font-size: 1rem;
}

.checkout-totals :deep(.v-field) {
	border-radius: var(--pos-radius-sm);
	background: var(--pos-surface-raised);
}
</style>
