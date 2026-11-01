<template>
	<div class="selection-fields">
		<!-- Sales Person Selection Card -->
		<div class="sales-person-card" :class="{ 'sales-person-card--unselected': !salesPerson }">
			<div class="sales-person-header">
				<div class="d-flex align-center gap-1">
					<v-icon icon="mdi-account-tie" size="18" :color="salesPerson ? 'primary' : 'warning'" />
					<span class="sales-person-title">{{ $frappe._("Продавец") }}</span>
					<span class="text-error font-weight-bold ml-1" title="Обязательное поле">*</span>
				</div>
				<v-chip
					v-if="salesPersons && salesPersons.length > 0"
					size="x-small"
					variant="tonal"
					:color="salesPerson ? 'primary' : 'warning'"
					class="font-weight-bold"
				>
					{{ salesPerson ? `${salesPersons.length} ${$__("доступно")}` : $__("Обязательно") }}
				</v-chip>
				<span v-else class="text-caption text-grey">
					{{ $__("Продавцы не найдены") }}
				</span>
			</div>

			<v-select
				density="compact"
				clearable
				variant="solo"
				color="primary"
				:placeholder="$frappe._('Выберите продавца...')"
				:model-value="salesPerson"
				:items="salesPersons"
				item-title="title"
				item-value="value"
				class="sleek-field pos-themed-input sales-person-select"
				:no-data-text="$__('Продавцы не найдены')"
				hide-details
				:disabled="readonly"
				prepend-inner-icon="mdi-account-outline"
				@update:model-value="$emit('update:sales-person', $event)"
			></v-select>
		</div>

		<!-- Print Format Selection (if shown) -->
		<div v-if="showPrintFormat" class="print-format-card mt-2">
			<div class="sales-person-header">
				<div class="d-flex align-center gap-2">
					<v-icon icon="mdi-printer" size="18" color="primary" />
					<span class="sales-person-title">{{ $frappe._("Формат печати") }}</span>
				</div>
			</div>
			<v-select
				density="compact"
				clearable
				variant="solo"
				color="primary"
				:placeholder="$frappe._('Формат печати')"
				:model-value="printFormat"
				:items="printFormats"
				class="sleek-field pos-themed-input"
				:no-data-text="$__('Форматы не найдены')"
				hide-details
				prepend-inner-icon="mdi-file-document-outline"
				@update:model-value="$emit('update:print-format', $event)"
			></v-select>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue";

defineProps({
	salesPersons: {
		type: Array,
		default: () => [],
	},
	salesPerson: {
		type: String,
		default: "",
	},
	readonly: {
		type: Boolean,
		default: false,
	},
	printFormats: {
		type: Array,
		default: () => [],
	},
	printFormat: {
		type: String,
		default: "",
	},
	showPrintFormat: {
		type: Boolean,
		default: true,
	},
});

defineEmits(["update:sales-person", "update:print-format"]);

const $frappe = inject("frappe", window.frappe);
const $__ = inject("__", window.__);
</script>

<style scoped>
.sales-person-card,
.print-format-card {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 12px 14px;
	border-radius: var(--pos-radius-md, 12px);
	background: #ffffff;
	border: 1px solid var(--pos-border-light, #e2e8f0);
	transition: all 0.2s ease;
}

.sales-person-card:hover {
	border-color: rgba(var(--v-theme-primary), 0.35);
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.sales-person-card--unselected {
	border-color: #fde68a;
	background: #fffdf5;
}

.sales-person-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.sales-person-title {
	font-size: 0.88rem;
	font-weight: 700;
	color: var(--pos-text-primary, #0f172a);
}

.sales-person-select :deep(.v-field) {
	border-radius: 8px !important;
}

.pos-themed-input :deep(.v-field__input) {
	font-weight: 600;
	font-size: 0.95rem;
}
</style>
