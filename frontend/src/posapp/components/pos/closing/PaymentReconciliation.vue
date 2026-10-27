<template>
	<div class="reconciliation-section">
		<div class="table-header mb-4">
			<h4 class="text-h6 text-grey-darken-2 mb-1">
				{{ __("Payment Reconciliation") }}
			</h4>
			<p class="text-body-2 text-grey">
				{{ __("Verify closing amounts for each payment method") }}
			</p>
		</div>

		<v-data-table
			:headers="headers"
			:items="payments"
			item-key="mode_of_payment"
			class="elevation-0 rounded-lg white-table"
			:items-per-page="itemsPerPage"
			hide-default-footer
			density="compact"
		>
			<template v-slot:item.closing_amount="props">
				<v-text-field
					v-model="props.item.closing_amount"
					:rules="[closingAmountRule]"
					:label="$frappe._('Edit')"
					single-line
					counter
					type="number"
					density="compact"
					variant="outlined"
					color="primary"
					class="pos-themed-input"
					hide-details
					:prefix="companyCurrencySymbol"
				></v-text-field>
			</template>
			<template v-slot:item.difference="{ item }">
				<div class="d-flex flex-column align-end">
					<span class="font-weight-medium">
						{{ companyCurrencySymbol }}
						{{ formatCurrency(calculateDifference(item)) }}
					</span>
					<v-chip
						size="x-small"
						:color="getDiscrepancyLabel(item).color"
						variant="flat"
						class="mt-1 font-weight-bold"
					>
						{{ getDiscrepancyLabel(item).text }}
					</v-chip>
				</div>
			</template>
			<template v-slot:item.opening_amount="{ item }">
				{{ companyCurrencySymbol }}
				{{ formatCurrency(item.opening_amount) }}</template
			>
			<template v-slot:item.expected_amount="{ item }">
				{{ companyCurrencySymbol }}
				{{ formatCurrency(item.expected_amount) }}</template
			>
			<template v-slot:item.variance_percent="{ item }">
				<span :class="['variance-chip', varianceClass(item)]">
					{{ formatVariancePercent(item) }}
				</span>
			</template>
		</v-data-table>
	</div>
</template>

<script setup>
import { inject } from "vue";

const props = defineProps({
	payments: Array,
	headers: Array,
	itemsPerPage: {
		type: Number,
		default: 20,
	},
	companyCurrencySymbol: String,
	// Formatters
	formatCurrency: Function,
	formatFloat: Function,
});

const $frappe = inject("frappe", window.frappe);
const __ = window.__ || ((t) => t);

const closingAmountRule = (v) => {
	if (v === "" || v === null || v === undefined) {
		return true;
	}

	const value = typeof v === "number" ? v : Number(String(v).trim());

	if (!Number.isFinite(value)) {
		return "Please enter a valid number";
	}

	const stringValue = String(v);
	const [integerPart, fractionalPart] = stringValue.split(".");

	if (integerPart.replace(/^-/, "").length > 20) {
		return "Number is too large";
	}

	if (fractionalPart && fractionalPart.length > 2) {
		return "Maximum of 2 decimal places";
	}

	return true;
};

const calculateDifference = (item) => {
	const closing = Number(item?.closing_amount) || 0;
	const expected = Number(item?.expected_amount) || 0;
	return expected - closing;
};

const formatVariancePercent = (item) => {
	const expected = Number(item?.expected_amount) || 0;
	if (!expected) {
		const closing = Number(item?.closing_amount) || 0;
		return closing ? __("N/A") : "0%";
	}
	const variance = (calculateDifference(item) / expected) * 100;
	const prefix = variance > 0 ? "+" : variance < 0 ? "" : "";
	return `${prefix}${props.formatFloat(variance, 2)}%`;
};

const varianceClass = (item) => {
	const expected = Number(item?.expected_amount) || 0;
	if (!expected) {
		return "variance-neutral";
	}
	const variance = (calculateDifference(item) / expected) * 100;
	if (!variance) {
		return "variance-neutral";
	}
	return variance > 0 ? "variance-negative" : "variance-positive";
};

const getDiscrepancyLabel = (item) => {
	const closing = Number(item?.closing_amount);
	const expected = Number(item?.expected_amount) || 0;
	if (item?.closing_amount === "" || item?.closing_amount === undefined || isNaN(closing)) {
		return { text: __("Не введено"), color: "grey" };
	}
	const diff = closing - expected;
	if (Math.abs(diff) < 0.001) {
		return { text: __("В кассе сошлось (0)"), color: "success" };
	} else if (diff > 0) {
		return { text: `+${props.formatCurrency(diff)} ${__("Излишек")}`, color: "info" };
	} else {
		return { text: `${props.formatCurrency(diff)} ${__("Недостача")}`, color: "error" };
	}
};
</script>

<style scoped>
.white-table {
	background: rgb(var(--v-theme-surface)) !important;
	border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.pos-themed-input :deep(.v-field__outline__start),
.pos-themed-input :deep(.v-field__outline__end) {
	border-color: rgba(var(--v-border-color), var(--v-border-opacity)) !important;
}

.variance-chip {
	display: inline-block;
	padding: 4px 12px;
	border-radius: 12px;
	font-size: 0.75rem;
	font-weight: 600;
	letter-spacing: 0.5px;
}

.variance-positive {
	background-color: rgba(var(--v-theme-success), 0.1);
	color: rgb(var(--v-theme-success));
}

.variance-negative {
	background-color: rgba(var(--v-theme-error), 0.1);
	color: rgb(var(--v-theme-error));
}

.variance-neutral {
	background-color: rgba(var(--v-theme-on-surface), 0.05);
	opacity: 0.7;
}
</style>
