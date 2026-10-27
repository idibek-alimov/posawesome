<template>
	<v-dialog :model-value="modelValue" max-width="540px" persistent>
		<v-card class="fiscal-fallback-card elevation-12">
			<v-card-item class="bg-amber-lighten-5 pa-4">
				<template #prepend>
					<div class="warning-icon-wrapper">
						<v-icon icon="mdi-printer-alert" color="amber-darken-3" size="32" />
					</div>
				</template>
				<v-card-title class="text-h6 font-weight-bold text-amber-darken-4">
					{{ __("Фискальный принтер недоступен") }}
				</v-card-title>
				<v-card-subtitle class="text-body-2 text-grey-darken-2 mt-1">
					{{ __("Чек не был зарегистрирован в налоговом накопителе (ФН / ОФД)") }}
				</v-card-subtitle>
			</v-card-item>

			<v-card-text class="pa-5">
				<p class="text-body-1 text-grey-darken-3 mb-3">
					{{ __("Связь с фискальным принтером TP809 прервана. Проверьте питание, наличие кассовой ленты и сетевое подключение.") }}
				</p>

				<v-alert
					v-if="errorMessage"
					type="error"
					variant="tonal"
					density="compact"
					class="mb-4 text-caption font-mono"
				>
					<strong>{{ __("Ошибка связи:") }}</strong> {{ errorMessage }}
				</v-alert>

				<div class="guidance-box pa-3 rounded-lg bg-grey-lighten-4">
					<div class="text-subtitle-2 font-weight-bold mb-1">
						{{ __("Выберите действие:") }}
					</div>
					<ul class="text-body-2 text-grey-darken-2 pl-4">
						<li><strong>{{ __("Повторить:") }}</strong> {{ __("отправить команду печати чека повторно.") }}</li>
						<li><strong>{{ __("Пробить без чека:") }}</strong> {{ __("провести продажу в системе без фискального чека.") }}</li>
					</ul>
				</div>
			</v-card-text>

			<v-divider></v-divider>

			<v-card-actions class="pa-4 bg-grey-lighten-5">
				<v-btn
					variant="outlined"
					color="grey-darken-1"
					@click="$emit('cancel')"
					:disabled="loading"
				>
					{{ __("Отмена") }}
				</v-btn>
				<v-spacer></v-spacer>
				<v-btn
					variant="tonal"
					color="warning"
					class="mr-2"
					@click="$emit('skip-fiscal')"
					:disabled="loading"
				>
					<v-icon start icon="mdi-flash" />
					{{ __("Пробить без чека") }}
				</v-btn>
				<v-btn
					variant="flat"
					color="primary"
					@click="$emit('retry')"
					:loading="loading"
				>
					<v-icon start icon="mdi-refresh" />
					{{ __("Повторить") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
defineProps({
	modelValue: Boolean,
	errorMessage: {
		type: String,
		default: "",
	},
	loading: Boolean,
});

defineEmits(["retry", "skip-fiscal", "cancel"]);

const __ = window.__ || ((t) => t);
</script>

<style scoped>
.fiscal-fallback-card {
	border-radius: 16px;
	overflow: hidden;
}

.warning-icon-wrapper {
	width: 48px;
	height: 48px;
	border-radius: 12px;
	background: rgba(245, 158, 11, 0.15);
	display: flex;
	align-items: center;
	justify-content: center;
	margin-right: 12px;
}

.font-mono {
	font-family: monospace;
}
</style>
