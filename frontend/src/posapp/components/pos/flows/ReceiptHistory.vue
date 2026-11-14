<template>
	<v-dialog v-model="open" max-width="1100" scrollable :persistent="printing">
		<v-card>
			<v-card-title class="d-flex align-center">{{ __('Чеки') }}<v-spacer /><v-btn icon="mdi-close" variant="text" :disabled="printing" :aria-label="__('Close')" @click="open = false" /></v-card-title>
			<v-card-text>
				<v-alert v-if="error" type="warning" variant="tonal" class="mb-3">{{ error }}</v-alert>
				<v-alert v-if="printing" type="info" variant="tonal" class="mb-3">{{ __('Подготовка товарного чека…') }}</v-alert>
				<PurchaseHistory v-if="open" :profile="profile" :disabled="printing" :action-label="__('Печать чека')" action-icon="mdi-printer" @select="printSale" />
			</v-card-text>
			<v-card-actions><v-spacer /><v-btn :disabled="printing" @click="open = false">{{ __('Закрыть') }}</v-btn></v-card-actions>
		</v-card>
	</v-dialog>
</template>
<script>
import PurchaseHistory from "./PurchaseHistory.vue";
import { useUIStore } from "../../../stores/uiStore";
import { printMarketReceipt } from "../../../services/marketReceipt";

export default {
	components: { PurchaseHistory },
	setup() { return { uiStore: useUIStore() }; },
	data: () => ({ open: false, printing: false, error: "" }),
	computed: { profile() { return this.uiStore.posProfile || {}; } },
	methods: {
		openReceipts() { this.error = ""; this.open = true; },
		async printSale(sale) {
			if (this.printing) return;
			this.printing = true; this.error = "";
			try { await printMarketReceipt(sale, this.profile); }
			catch (error) { this.error = error.message; }
			finally { this.printing = false; }
		},
	},
	created() { this.eventBus.on("open_receipts", this.openReceipts); },
	beforeUnmount() { this.eventBus.off("open_receipts", this.openReceipts); },
};
</script>
