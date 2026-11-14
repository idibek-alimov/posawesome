<template>
	<v-dialog :model-value="modelValue" max-width="560" persistent>
		<v-card>
			<v-card-title>{{ __("Проверьте результат фискализации") }}</v-card-title>
			<v-card-text>
				<p>{{ unknownOutcome ? __("Продажа сохранена. Результат фискализации не подтверждён. Проверьте журнал принтера перед повторной отправкой.") : __("Sale saved. No fiscal receipt was issued. Resolve the printer error and try again.") }}</p>
				<v-alert v-if="errorMessage" type="warning" variant="tonal" class="mt-3">{{ errorMessage }}</v-alert>
			</v-card-text>
			<v-card-actions class="fiscal-recovery-actions">
				<v-btn @click="$emit('cancel')">{{ __("Закрыть") }}</v-btn><v-spacer />
				<v-btn v-if="unknownOutcome" :loading="loading" @click="$emit('reconcile')">{{ __("Проверить ФД №") }}</v-btn>
				<v-btn v-if="unknownOutcome" :disabled="loading" @click="$emit('no-document')">{{ __("В журнале нет чека") }}</v-btn>
				<v-btn :loading="loading" @click="$emit('retry')">{{ unknownOutcome ? __("Восстановить результат") : __("Retry") }}</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>
<script setup>
defineProps({ modelValue: Boolean, errorMessage: String, loading: Boolean, unknownOutcome: { type: Boolean, default: true } });
defineEmits(["retry", "reconcile", "no-document", "cancel"]);
const __ = window.__ || ((text) => text);
</script>
<style scoped>
.fiscal-recovery-actions { flex-wrap: wrap; gap: 4px; }
</style>
