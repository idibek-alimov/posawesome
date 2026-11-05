<template>
	<v-card-title class="closing-header">
		<div>
			<h2 id="closing-dialog-title" class="text-h6">{{ __("Close shift") }}</h2>
			<p class="text-body-2 text-medium-emphasis">{{ profile }} · {{ cashier }}</p>
			<p v-if="openedAt" class="text-caption text-medium-emphasis">
				{{ __("Opened") }}: {{ openedAt }}
			</p>
		</div>
		<v-btn
			icon="mdi-close"
			variant="text"
			:disabled="busy"
			:aria-label="__('Cancel')"
			@click="$emit('close')"
		/>
	</v-card-title>
</template>
<script setup>
defineProps({ profile: String, cashier: String, openedAt: String, busy: Boolean });
defineEmits(["close"]);
const __ = window.__ || ((text) => text);
</script>
<style scoped>
.closing-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 16px;
	padding: 20px 24px 12px;
	white-space: normal;
}
</style>
