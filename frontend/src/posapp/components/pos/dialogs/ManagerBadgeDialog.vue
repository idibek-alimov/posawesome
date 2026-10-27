<template>
	<v-dialog :model-value="modelValue" max-width="480px" persistent>
		<v-card class="manager-badge-card elevation-12">
			<v-card-item class="bg-indigo-lighten-5 pa-4">
				<template #prepend>
					<div class="shield-icon-wrapper">
						<v-icon icon="mdi-shield-lock" color="indigo-darken-3" size="32" />
					</div>
				</template>
				<v-card-title class="text-h6 font-weight-bold text-indigo-darken-4">
					{{ __("Авторизация администратора") }}
				</v-card-title>
				<v-card-subtitle class="text-body-2 text-grey-darken-2 mt-1">
					{{ __("Для установки ручной скидки требуется подтверждение") }}
				</v-card-subtitle>
			</v-card-item>

			<v-card-text class="pa-5 text-center">
				<div class="scanner-visual my-3">
					<v-icon icon="mdi-barcode-scan" size="64" color="indigo-darken-1" class="pulse-animation" />
					<div class="text-h6 font-weight-bold mt-2 text-grey-darken-3">
						{{ __("Отсканируйте бейдж администратора") }}
					</div>
					<div class="text-caption text-grey mt-1">
						{{ __("Префикс штрихкода: MGR-...") }}
					</div>
				</div>

				<v-divider class="my-4"></v-divider>

				<v-form @submit.prevent="submitManualCode">
					<v-text-field
						v-model="inputCode"
						:label="__('Или введите код бейджа вручную')"
						placeholder="MGR-ADMIN"
						variant="outlined"
						density="comfortable"
						color="primary"
						prepend-inner-icon="mdi-badge-account"
						autofocus
						:loading="loading"
						hide-details="auto"
						class="mb-3"
					/>
				</v-form>
			</v-card-text>

			<v-card-actions class="pa-4 bg-grey-lighten-5">
				<v-btn
					variant="text"
					color="grey-darken-1"
					@click="cancel"
				>
					{{ __("Отмена") }}
				</v-btn>
				<v-spacer></v-spacer>
				<v-btn
					variant="flat"
					color="primary"
					@click="submitManualCode"
					:loading="loading"
					:disabled="!inputCode.trim()"
				>
					{{ __("Подтвердить") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	modelValue: Boolean,
	loading: Boolean,
});

const emit = defineEmits(["update:modelValue", "verified", "cancel"]);

const inputCode = ref("");
const __ = window.__ || ((t) => t);

const submitManualCode = () => {
	if (!inputCode.value.trim()) return;
	emit("verified", inputCode.value.trim());
	inputCode.value = "";
};

const cancel = () => {
	inputCode.value = "";
	emit("update:modelValue", false);
	emit("cancel");
};
</script>

<style scoped>
.manager-badge-card {
	border-radius: 16px;
	overflow: hidden;
}

.shield-icon-wrapper {
	width: 48px;
	height: 48px;
	border-radius: 12px;
	background: rgba(79, 70, 229, 0.15);
	display: flex;
	align-items: center;
	justify-content: center;
	margin-right: 12px;
}

.pulse-animation {
	animation: pulse-scan 2s infinite ease-in-out;
}

@keyframes pulse-scan {
	0%, 100% {
		transform: scale(1);
		opacity: 0.9;
	}
	50% {
		transform: scale(1.08);
		opacity: 1;
	}
}
</style>
