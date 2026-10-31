<template>
	<v-card
		class="cards item-action-toolbar-card pos-bottom-bar mb-0 mt-3 py-2 px-3 rounded-lg pos-themed-card"
		:class="{ 'cards--with-mobile-offset': reserveBottomDockSpace }"
	>
		<div class="toolbar-inner-container">
			<!-- Row 1: Items Group selection -->
			<div class="toolbar-row toolbar-row--select">
				<v-select
					:items="itemsGroup"
					:label="frappe._('Items Group')"
					density="compact"
					variant="solo"
					hide-details
					:model-value="modelValue"
					class="item-group-select"
					@update:model-value="$emit('update:modelValue', $event)"
				></v-select>
			</div>

			<!-- Row 2: View toggle (List/Card) + Offers + Coupons -->
			<div class="toolbar-row toolbar-row--actions">
				<v-btn-toggle
					:model-value="itemsView"
					@update:model-value="$emit('update:itemsView', $event)"
					color="primary"
					group
					density="compact"
					rounded
					class="view-toggle-btn"
				>
					<v-btn size="small" value="list">{{ __("List") }}</v-btn>
					<v-btn size="small" value="card">{{ __("Card") }}</v-btn>
				</v-btn-toggle>

				<div class="toolbar-badge-buttons">
					<v-btn
						size="small"
						color="warning"
						variant="tonal"
						@click="$emit('open-offers')"
						class="action-btn-consistent"
					>
						<v-icon start size="16">mdi-tag-outline</v-icon>
						{{ offersCount }} {{ __("Offers") }}
					</v-btn>

					<v-btn
						size="small"
						color="primary"
						variant="tonal"
						@click="$emit('open-coupons')"
						class="action-btn-consistent"
					>
						<v-icon start size="16">mdi-ticket-percent-outline</v-icon>
						{{ couponsCount }} {{ __("Coupons") }}
					</v-btn>
				</div>
			</div>
		</div>
	</v-card>
</template>

<script setup>
const __ = window.__;
const frappe = window.frappe;

defineProps({
	modelValue: { type: String, default: "ALL" }, // item_group
	itemsGroup: { type: Array, default: () => [] },
	itemsView: { type: String, default: "card" },
	posProfile: { type: Object, required: true },
	activePriceList: { type: String, default: "" },
	offersCount: { type: Number, default: 0 },
	couponsCount: { type: Number, default: 0 },
	reserveBottomDockSpace: { type: Boolean, default: false },
});

defineEmits(["update:modelValue", "update:itemsView", "open-offers", "open-coupons"]);
</script>

<style scoped>
.item-action-toolbar-card {
	background-color: var(--pos-surface-muted) !important;
	border: 1px solid var(--pos-border-light);
	position: sticky;
	bottom: 0;
	z-index: 7;
	min-width: 0;
	overflow: hidden;
}

@media (min-width: 960px) {
	.pos-bottom-bar {
		height: var(--bottom-bar-height, 108px) !important;
		min-height: var(--bottom-bar-height, 108px) !important;
		max-height: var(--bottom-bar-height, 108px) !important;
		box-sizing: border-box;
	}
}

.toolbar-inner-container {
	display: flex;
	flex-direction: column;
	justify-content: space-between;
	height: 100%;
	gap: 6px;
}

.toolbar-row--select {
	flex: 0 0 auto;
}

.toolbar-row--select :deep(.v-field) {
	border-radius: var(--pos-radius-sm, 6px);
}

.toolbar-row--actions {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
	flex: 0 0 auto;
}

.toolbar-badge-buttons {
	display: flex;
	align-items: center;
	gap: 8px;
}

.action-btn-consistent {
	height: 32px !important;
	min-height: 32px !important;
	padding: 0 12px !important;
	border-radius: var(--pos-radius-sm, 6px) !important;
	text-transform: none !important;
	font-weight: 600 !important;
	font-size: 0.8rem !important;
	transition: var(--transition-normal) !important;
}

.action-btn-consistent:hover {
	transform: translateY(-1px);
}

.view-toggle-btn {
	height: 32px !important;
	border: 1px solid var(--pos-border-light);
	border-radius: var(--pos-radius-sm, 6px);
}

.view-toggle-btn :deep(.v-btn) {
	height: 30px !important;
	font-size: 0.78rem !important;
	font-weight: 600 !important;
}

.cards--with-mobile-offset {
	margin-bottom: calc(var(--bottom-safe-space) + 6px) !important;
}

@media (max-width: 1099px) {
	.item-action-toolbar-card {
		position: static;
	}
}

@media (max-width: 768px) {
	.toolbar-row--actions {
		flex-wrap: wrap;
	}

	.view-toggle-btn {
		width: 100%;
	}

	.toolbar-badge-buttons {
		width: 100%;
		justify-content: space-between;
	}

	.action-btn-consistent {
		flex: 1;
	}
}

@media (max-width: 480px) {
	.item-action-toolbar-card {
		padding: var(--dynamic-xs) !important;
		position: static;
	}
}
</style>
