<template>
	<v-dialog
		:model-value="modelValue"
		max-width="420"
		@update:model-value="$emit('update:modelValue', $event)"
	>
		<v-card
			class="pos-themed-card posa-remove-dialog"
			tabindex="0"
			@keydown.enter.stop.prevent="handleConfirm"
			@keydown.esc.stop.prevent="handleCancel"
		>
			<v-card-title class="d-flex align-center pb-2 pt-4 px-5">
				<div class="posa-remove-dialog__icon-wrap mr-3">
					<v-icon color="error" size="24">mdi-trash-can-outline</v-icon>
				</div>
				<span class="text-h6 font-weight-bold">{{ __("Remove Product?") }}</span>
			</v-card-title>

			<v-card-text class="pt-2 pb-4 px-5">
				<div class="text-body-1 text-medium-emphasis mb-2">
					{{ __("Do you want to remove this product from the cart?") }}
				</div>
				<div v-if="itemName" class="posa-remove-dialog__item-name">
					{{ itemName }}
				</div>
			</v-card-text>

			<v-card-actions class="px-5 pb-4 pt-0">
				<v-spacer />
				<v-btn
					variant="text"
					class="px-4"
					@click="handleCancel"
				>
					{{ __("Cancel") }}
				</v-btn>
				<v-btn
					color="error"
					variant="elevated"
					class="px-4 font-weight-bold"
					ref="confirmBtn"
					@click="handleConfirm"
				>
					{{ __("Yes, Remove") }}
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
}>();

const emit = defineEmits<{
	"update:modelValue": [value: boolean];
	confirm: [item: any];
	cancel: [];
}>();

const confirmBtn = ref<any>(null);

const itemName = computed(() => {
	return props.item?.item_name || props.item?.item_code || "";
});

watch(
	() => props.modelValue,
	(isOpen) => {
		if (isOpen) {
			nextTick(() => {
				setTimeout(() => {
					confirmBtn.value?.$el?.focus?.();
				}, 60);
			});
		}
	},
);

const handleCancel = () => {
	emit("cancel");
	emit("update:modelValue", false);
};

const handleConfirm = () => {
	emit("confirm", props.item);
	emit("update:modelValue", false);
};
</script>

<style scoped>
.posa-remove-dialog__icon-wrap {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 40px;
	height: 40px;
	border-radius: 10px;
	background: rgba(239, 68, 68, 0.12);
}

.posa-remove-dialog__item-name {
	font-weight: 700;
	font-size: 1.05rem;
	color: var(--pos-text-primary, #0f172a);
	padding: 10px 14px;
	background: var(--pos-surface-variant, rgba(0, 0, 0, 0.04));
	border-radius: 8px;
	border-left: 4px solid var(--pos-error, #ef4444);
	margin-top: 8px;
	word-break: break-word;
}
</style>
