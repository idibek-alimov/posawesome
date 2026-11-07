<template>
	<section aria-labelledby="closing-money-title">
		<h3 id="closing-money-title" class="text-subtitle-1 font-weight-medium mb-1">
			{{ __("Money to reconcile") }}
		</h3>
		<p class="text-body-2 text-medium-emphasis mb-3">
			{{ __("Count cash and check each payment method's closing amount after withdrawals.") }}
		</p>
		<div class="money-table-wrapper">
			<table class="money-table">
				<caption class="text-caption text-medium-emphasis">
					{{
						__("All amounts in {0}", [currency])
					}}
				</caption>
				<thead>
					<tr>
						<th scope="col">{{ __("Payment method") }}</th>
						<th scope="col">{{ __("At opening") }}</th>
						<th v-if="!hideExpected" scope="col">{{ __("Net received") }}</th>
						<th v-if="!hideExpected" scope="col">{{ __("Taken out") }}</th>
						<th v-if="!hideExpected" scope="col">{{ __("Expected") }}</th>
						<th scope="col">{{ __("Actual") }}</th>
						<th v-if="!hideExpected" scope="col">{{ __("Difference") }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="item in payments" :key="item.mode_of_payment">
						<th scope="row" class="method-cell">
							<span>{{ item.mode_of_payment }}</span>
							<span
								v-if="item.account"
								class="account-name text-caption text-medium-emphasis"
								>{{ item.account }}</span
							>
						</th>
						<td :data-label="__('At opening')">{{ formatCurrency(item.opening_amount) }}</td>
						<td v-if="!hideExpected" :data-label="__('Net received')">
							{{ formatCurrency(item.net_received) }}
						</td>
						<td v-if="!hideExpected" :data-label="__('Taken out')">
							{{ formatCurrency(item.taken_out) }}
						</td>
						<td v-if="!hideExpected" :data-label="__('Expected')" class="font-weight-bold">
							{{ formatCurrency(item.expected_amount) }}
						</td>
						<td :data-label="__('Actual')" class="actual-cell">
							<v-text-field
								v-model="item.closing_amount"
								:disabled="busy"
								type="number"
								:step="10 ** -precision"
								density="compact"
								variant="outlined"
								hide-details
								:aria-label="__('Actual amount: {0}', [item.mode_of_payment])"
								:error="
									item.closing_amount !== '' &&
									item.closing_amount != null &&
									actualAmount(item.closing_amount, precision) === null
								"
							/>
						</td>
						<td v-if="!hideExpected" :data-label="__('Difference')">
							<span v-if="difference(item) === null" class="text-medium-emphasis">—</span>
							<span
								v-else
								:class="
									difference(item) < 0
										? 'text-error'
										: difference(item) > 0
											? 'text-info'
											: ''
								"
							>
								{{ formatCurrency(difference(item)) }}
								<span v-if="difference(item)" class="difference-label text-caption">{{
									difference(item) < 0 ? __("Shortage") : __("Surplus")
								}}</span>
							</span>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<p v-if="!hideExpected" class="text-caption text-medium-emphasis mt-2">
			{{
				__("Net received includes refunds and change. Expected = opening + net received − taken out.")
			}}
		</p>
	</section>
</template>
<script setup>
import { actualAmount, closingDifference } from "../../../composables/pos/closing/closingAmounts";
const props = defineProps({
	payments: { type: Array, default: () => [] },
	currency: String,
	precision: { type: Number, default: 3 },
	hideExpected: Boolean,
	busy: Boolean,
	formatCurrency: Function,
});
const __ = window.__ || ((text) => text);
const difference = (row) => closingDifference(row, props.precision);
</script>
<style scoped>
.money-table-wrapper {
	overflow-x: auto;
	border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
	border-radius: 6px;
}
.money-table {
	border-collapse: collapse;
	width: 100%;
	font-size: 0.875rem;
	font-variant-numeric: tabular-nums;
}
.money-table caption {
	text-align: end;
	padding: 8px 12px 0;
}
.money-table th,
.money-table td {
	padding: 10px 12px;
	text-align: end;
	border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.money-table thead th {
	font-weight: 500;
	color: rgb(var(--v-theme-on-surface));
	white-space: nowrap;
}
.money-table .method-cell,
.money-table thead th:first-child {
	text-align: start;
}
.method-cell {
	font-weight: 500;
	max-width: 220px;
}
.account-name,
.difference-label {
	display: block;
}
.actual-cell {
	min-width: 120px;
	width: 140px;
}
.actual-cell :deep(input) {
	text-align: end;
	font-variant-numeric: tabular-nums;
}
.money-table tbody tr:last-child > * {
	border-bottom: 0;
}
@media (max-width: 700px) {
	.money-table thead {
		display: none;
	}
	.money-table tbody {
		display: block;
	}
	.money-table tr {
		display: grid;
		grid-template-columns: 1fr 1fr;
		padding: 12px;
		gap: 12px;
		border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
	}
	.money-table tr:last-child {
		border: 0;
	}
	.money-table th,
	.money-table td {
		display: block;
		padding: 0;
		border: 0;
		text-align: start;
	}
	.money-table .method-cell {
		grid-column: 1 / -1;
		max-width: none;
	}
	.money-table td::before {
		content: attr(data-label);
		display: block;
		font-size: 0.75rem;
		opacity: 0.7;
		margin-bottom: 4px;
	}
	.actual-cell {
		width: auto;
		min-width: 0;
	}
}
</style>
