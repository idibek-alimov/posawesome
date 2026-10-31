<template>
	<v-dialog
		:model-value="modelValue"
		max-width="380"
		transition="dialog-bottom-transition"
		@update:model-value="$emit('update:modelValue', $event)"
	>
		<v-card class="pos-themed-card posa-qty-keypad-card" @keydown="handleKeyDown" tabindex="0" ref="cardRef">
			<v-card-title class="d-flex align-center justify-space-between pb-1 pt-3 px-4">
				<div class="d-flex align-center">
					<v-icon color="primary" class="mr-2" size="22">mdi-numeric</v-icon>
					<span class="text-subtitle-1 font-weight-bold">{{ __("Set Quantity") }}</span>
				</div>
				<v-btn
					icon="mdi-close"
					size="x-small"
					variant="text"
					@click="handleCancel"
					:aria-label="__('Close')"
				/>
			</v-card-title>

			<v-card-text class="pt-1 pb-2 px-4">
				<div class="posa-qty-keypad__item-meta mb-3">
					<div class="posa-qty-keypad__item-name">{{ itemName }}</div>
					<div v-if="uom" class="text-caption text-medium-emphasis">
						{{ __("Unit") }}: <strong>{{ uom }}</strong>
					</div>
				</div>

				<!-- Value display -->
				<div class="posa-qty-keypad__display mb-3">
					<span class="posa-qty-keypad__display-value">{{ displayValue }}</span>
					<span v-if="uom" class="posa-qty-keypad__display-uom">{{ uom }}</span>
				</div>

				<!-- Quick Add Chips -->
				<div class="posa-qty-keypad__quick-chips mb-3">
					<v-chip
						size="small"
						variant="tonal"
						color="primary"
						class="font-weight-bold"
						@click="quickAdd(1)"
					>
						+1
					</v-chip>
					<v-chip
						size="small"
						variant="tonal"
						color="primary"
						class="font-weight-bold"
						@click="quickAdd(5)"
					>
						+5
					</v-chip>
					<v-chip
						size="small"
						variant="tonal"
						color="primary"
						class="font-weight-bold"
						@click="quickAdd(10)"
					>
						+10
					</v-chip>
					<v-chip
						size="small"
						variant="tonal"
						color="primary"
						class="font-weight-bold"
						@click="quickAdd(20)"
					>
						+20
					</v-chip>
				</div>

				<!-- Numpad Grid -->
				<div class="posa-qty-keypad__grid">
					<v-btn
						v-for="digit in ['7', '8', '9']"
						:key="digit"
						class="posa-qty-keypad__btn"
						variant="tonal"
						@click="appendDigit(digit)"
					>
						{{ digit }}
					</v-btn>
					<v-btn
						class="posa-qty-keypad__btn posa-qty-keypad__btn--action"
						variant="tonal"
						color="error"
						@click="handleBackspace"
						:aria-label="__('Backspace')"
					>
						<v-icon size="20">mdi-backspace-outline</v-icon>
					</v-btn>

					<v-btn
						v-for="digit in ['4', '5', '6']"
						:key="digit"
						class="posa-qty-keypad__btn"
						variant="tonal"
						@click="appendDigit(digit)"
					>
						{{ digit }}
					</v-btn>
					<v-btn
						class="posa-qty-keypad__btn posa-qty-keypad__btn--action font-weight-bold"
						variant="tonal"
						color="warning"
						@click="handleClear"
						:aria-label="__('Clear')"
					>
						C
					</v-btn>

					<v-btn
						v-for="digit in ['1', '2', '3']"
						:key="digit"
						class="posa-qty-keypad__btn"
						variant="tonal"
						@click="appendDigit(digit)"
					>
						{{ digit }}
					</v-btn>
					<v-btn
						class="posa-qty-keypad__btn font-weight-bold"
						variant="tonal"
						@click="appendDigit('.')"
						:disabled="hideDecimals || currentValue.includes('.')"
					>
						.
					</v-btn>

					<v-btn
						class="posa-qty-keypad__btn"
						variant="tonal"
						@click="appendDigit('0')"
					>
						0
					</v-btn>
					<v-btn
						class="posa-qty-keypad__btn"
						variant="tonal"
						@click="appendDigit('00')"
					>
						00
					</v-btn>
				</div>
			</v-card-text>

			<v-card-actions class="px-4 pb-3 pt-0">
				<v-btn
					variant="text"
					class="px-4"
					@click="handleCancel"
				>
					{{ __("Cancel") }}
				</v-btn>
				<v-spacer />
				<v-btn
					color="primary"
					variant="elevated"
					class="px-6 font-weight-bold"
					@click="handleSubmit"
				>
					{{ __("Apply") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

// @ts-ignore
const __ = window.__ || ((text: string) => text);

const props = defineProps<{
	modelValue: boolean;
	item?: any;
	hideDecimals?: boolean;
}>();

const emit = defineEmits<{
	"update:modelValue": [value: boolean];
	submit: [value: number];
	cancel: [];
}>();

const cardRef = ref<any>(null);
const currentValue = ref("1");
const replaceOnNextInput = ref(true);

const itemName = computed(() => {
	return props.item?.item_name || props.item?.item_code || "";
});

const uom = computed(() => {
	return props.item?.uom || "";
});

const displayValue = computed(() => {
	return currentValue.value || "0";
});

watch(
	() => props.modelValue,
	(isOpen) => {
		if (isOpen) {
			const qty = Number(props.item?.qty ?? 1);
			currentValue.value = String(Number.isFinite(qty) ? qty : 1);
			replaceOnNextInput.value = true;
			nextTick(() => {
				setTimeout(() => {
					cardRef.value?.$el?.focus?.();
				}, 60);
			});
		}
	},
);

function appendDigit(val: string) {
	if (replaceOnNextInput.value) {
		if (val === ".") {
			currentValue.value = "0.";
		} else {
			currentValue.value = val;
		}
		replaceOnNextInput.value = false;
		return;
	}

	if (val === "." && currentValue.value.includes(".")) {
		return;
	}

	if (currentValue.value === "0" && val !== ".") {
		currentValue.value = val;
	} else {
		currentValue.value += val;
	}
}

function handleBackspace() {
	if (replaceOnNextInput.value) {
		currentValue.value = "0";
		replaceOnNextInput.value = false;
		return;
	}

	if (currentValue.value.length <= 1) {
		currentValue.value = "0";
		replaceOnNextInput.value = true;
	} else {
		currentValue.value = currentValue.value.slice(0, -1);
	}
}

function handleClear() {
	currentValue.value = "0";
	replaceOnNextInput.value = true;
}

function quickAdd(delta: number) {
	const current = parseFloat(currentValue.value) || 0;
	currentValue.value = String(current + delta);
	replaceOnNextInput.value = false;
}

function handleKeyDown(event: KeyboardEvent) {
	if (event.key >= "0" && event.key <= "9") {
		appendDigit(event.key);
		event.preventDefault();
	} else if (event.key === "." && !props.hideDecimals) {
		appendDigit(".");
		event.preventDefault();
	} else if (event.key === "Backspace") {
		handleBackspace();
		event.preventDefault();
	} else if (event.key === "Enter") {
		handleSubmit();
		event.preventDefault();
	} else if (event.key === "Escape") {
		handleCancel();
		event.preventDefault();
	}
}

function handleCancel() {
	emit("cancel");
	emit("update:modelValue", false);
}

function handleSubmit() {
	const parsed = parseFloat(currentValue.value);
	const finalQty = Number.isFinite(parsed) ? parsed : 1;
	emit("submit", finalQty);
	emit("update:modelValue", false);
}
</script>

<style scoped>
.posa-qty-keypad-card {
	outline: none;
}

.posa-qty-keypad__item-name {
	font-weight: 700;
	font-size: 1rem;
	color: var(--pos-text-primary, #0f172a);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.posa-qty-keypad__display {
	display: flex;
	align-items: baseline;
	justify-content: center;
	gap: 6px;
	padding: 12px 16px;
	background: var(--pos-surface-variant, rgba(0, 0, 0, 0.04));
	border: 2px solid var(--pos-primary, #1976d2);
	border-radius: 12px;
	min-height: 58px;
}

.posa-qty-keypad__display-value {
	font-size: 2rem;
	font-weight: 800;
	color: var(--pos-text-primary, #0f172a);
	font-variant-numeric: tabular-nums;
	letter-spacing: 0.5px;
}

.posa-qty-keypad__display-uom {
	font-size: 0.95rem;
	font-weight: 600;
	color: var(--pos-text-secondary, #64748b);
}

.posa-qty-keypad__quick-chips {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 8px;
}

.posa-qty-keypad__grid {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 8px;
}

.posa-qty-keypad__btn {
	height: 48px !important;
	font-size: 1.25rem !important;
	font-weight: 700 !important;
	border-radius: 10px !important;
	padding: 0 !important;
	min-width: 0 !important;
}

.posa-qty-keypad__btn--zero {
	grid-column: span 2;
}

.posa-qty-keypad__btn--action {
	font-size: 1.1rem !important;
}
</style>
