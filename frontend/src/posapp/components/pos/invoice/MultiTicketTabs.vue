<template>
	<div class="multi-ticket-container" role="tablist" :aria-label="__('Active Customer Carts')">
		<div class="multi-ticket-track">
			<button
				v-for="(slot, index) in slots"
				:key="slot.id"
				type="button"
				class="ticket-tab"
				:class="{
					'ticket-tab--active': activeSlotIndex === index,
					'ticket-tab--occupied': (slot.items?.length || 0) > 0,
					'ticket-tab--empty': (slot.items?.length || 0) === 0,
				}"
				role="tab"
				:aria-selected="activeSlotIndex === index"
				:aria-label="getSlotLabel(slot)"
				@click="onTabClick(index)"
			>
				<span class="ticket-tab__indicator" />
				<span class="ticket-tab__title">
					{{ getSlotLabel(slot) }}
				</span>

				<!-- Quick clear icon for non-empty inactive tabs or hovered active tab -->
				<span
					v-if="(slot.items?.length || 0) > 0"
					class="ticket-tab__clear-btn"
					role="button"
					:title="__('Clear Ticket')"
					@click.stop="confirmClearSlot(index)"
				>
					<svg class="clear-icon" viewBox="0 0 24 24" fill="currentColor">
						<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
					</svg>
				</span>
			</button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { getCurrentInstance } from "vue";
import { useMultiTickets, type TicketSlot } from "../../../composables/pos/invoice/useMultiTickets";

const props = defineProps<{
	posProfile?: any;
}>();

const instance = getCurrentInstance();
const eventBus = (instance?.proxy as any)?.eventBus || (instance?.appContext?.config?.globalProperties as any)?.eventBus;

const {
	slots,
	activeSlotIndex,
	getSlotLabel,
	switchToSlot,
	clearSlot,
} = useMultiTickets({
	posProfile: props.posProfile,
	eventBus,
});

function onTabClick(index: number) {
	switchToSlot(index);
}

function confirmClearSlot(index: number) {
	const slot = slots.value[index];
	if (!slot || (slot.items?.length || 0) === 0) return;

	const confirmMsg =
		typeof (globalThis as any).__ === "function"
			? (globalThis as any).__(`Clear Ticket №{0}?`, [index + 1])
			: `Clear Ticket №${index + 1}?`;

	if (window.confirm(confirmMsg)) {
		clearSlot(index);
	}
}
</script>

<style scoped>
.multi-ticket-container {
	display: flex;
	align-items: center;
	width: 100%;
	padding: 4px 6px 8px 6px;
	background: transparent;
	overflow-x: auto;
	scrollbar-width: none;
	user-select: none;
}

.multi-ticket-container::-webkit-scrollbar {
	display: none;
}

.multi-ticket-track {
	display: flex;
	gap: 6px;
	width: 100%;
	min-width: 0;
}

.ticket-tab {
	flex: 1;
	min-width: 0;
	height: 36px;
	padding: 0 10px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	position: relative;
	border-radius: 8px;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--pos-text-secondary, #666);
	background: var(--pos-surface-variant, #f5f5f5);
	border: 1px solid var(--pos-border, rgba(0, 0, 0, 0.08));
	cursor: pointer;
	transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.ticket-tab:hover {
	background: var(--pos-surface, #fff);
	border-color: var(--pos-primary, #0097a7);
	color: var(--pos-text-primary, #222);
}

.ticket-tab--occupied {
	border-color: rgba(0, 151, 167, 0.35);
	background: var(--pos-surface, #fff);
	font-weight: 600;
	color: var(--pos-text-primary, #111);
}

.ticket-tab--active {
	background: var(--pos-primary, #0097a7) !important;
	color: var(--pos-on-primary, #ffffff) !important;
	border-color: var(--pos-primary-variant, #00838f) !important;
	box-shadow: 0 2px 6px rgba(0, 151, 167, 0.28);
	font-weight: 600;
}

.ticket-tab__indicator {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	margin-right: 6px;
	flex-shrink: 0;
	background: transparent;
	transition: all 0.2s ease;
}

.ticket-tab--occupied .ticket-tab__indicator {
	background: #ff9800; /* Accent indicator for occupied carts */
}

.ticket-tab--active .ticket-tab__indicator {
	background: #ffffff; /* Crisp white dot on active */
	box-shadow: 0 0 4px rgba(255, 255, 255, 0.8);
}

.ticket-tab__title {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	line-height: 1;
}

.ticket-tab__clear-btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 18px;
	height: 18px;
	margin-left: 6px;
	border-radius: 50%;
	opacity: 0.6;
	transition: opacity 0.15s ease, background-color 0.15s ease;
	flex-shrink: 0;
}

.ticket-tab__clear-btn:hover {
	opacity: 1;
	background-color: rgba(0, 0, 0, 0.12);
}

.ticket-tab--active .ticket-tab__clear-btn:hover {
	background-color: rgba(255, 255, 255, 0.25);
}

.clear-icon {
	width: 14px;
	height: 14px;
}

@media (max-width: 600px) {
	.ticket-tab {
		padding: 0 6px;
		font-size: 0.75rem;
		height: 32px;
	}
	.ticket-tab__clear-btn {
		display: none;
	}
}
</style>
