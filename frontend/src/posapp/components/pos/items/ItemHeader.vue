<template>
	<div class="sticky-header">
		<v-row class="items align-center">
			<v-col
				class="py-0"
				:cols="posProfile.posa_input_qty ? 8 : 12"
				:sm="posProfile.posa_input_qty ? 9 : 12"
			>
				<div class="search-field-shell" @keydown.capture="handleSearchKeydownCapture">
					<v-text-field
						clearable
						autofocus
						variant="solo"
						color="primary"
						class="pos-themed-input product-search-input--hero"
						:placeholder="
							searchCombobox
								? __('Search saleable items')
								: 'Поиск или сканирование товара'
						"
						:aria-label="
							searchCombobox
								? __('Search saleable items')
								: 'Поиск или сканирование товара'
						"
						hide-details
						data-pos-keyboard-target="item-search"
						data-testid="pos-item-search"
						v-search-combobox="{
							enabled: searchCombobox,
							expanded: searchExpanded,
							controls: searchControls,
							activeDescendant: searchActiveDescendant,
							label: __('Search saleable items'),
						}"
						:model-value="searchInput"
						@update:model-value="
							(val) => {
								$emit('update:searchInput', val);
								$emit('search-input', val);
							}
						"
						@keydown="handleSearchKeydown"
						@click:clear="$emit('clear-search')"
						@click:prepend-inner="$emit('focus')"
						@paste="$emit('search-paste', $event)"
						prepend-inner-icon="mdi-magnify"
						@focus="$emit('focus')"
						ref="debounce_search"
					>
						<template v-slot:append-inner>
							<v-btn
								v-if="posProfile.posa_enable_camera_scanning"
								icon="mdi-camera"
								size="small"
								color="primary"
								variant="text"
								:disabled="scannerLocked"
								@click="$emit('start-camera')"
								:aria-label="
									scannerLocked
										? __(
												'Camera scanner is locked until the current error is acknowledged',
											)
										: __('Scan with camera')
								"
								:title="
									scannerLocked
										? __('Acknowledge the error to resume scanning')
										: __('Scan with Camera')
								"
							>
							</v-btn>
							<v-btn
								icon="mdi-tune-vertical"
								size="small"
								color="primary"
								variant="text"
								@click.stop="toolsOpen = !toolsOpen"
								:aria-label="toolsOpen ? __('Hide search tools') : __('Show search tools')"
							>
							</v-btn>
						</template>
					</v-text-field>
					<div
						v-if="showSyncProgress"
						class="search-sync-progress"
						data-test="item-search-sync-shell"
						aria-live="polite"
					>
						<v-progress-linear
							:model-value="clampedSyncProgress"
							height="3"
							rounded
							color="info"
							bg-color="rgba(15, 23, 42, 0.08)"
							data-test="item-search-sync-bar"
							:aria-label="__('Item sync progress')"
						/>
						<div class="search-sync-progress__meta">
							<span class="search-sync-progress__label">
								{{ syncStatus || __("Syncing items in background") }}
								<span v-if="normalizedSyncItemsCount > 0" class="search-sync-progress__count">
									{{ syncItemsCountLabel }}
								</span>
							</span>
							<span class="search-sync-progress__value"> {{ clampedSyncProgress }}% </span>
						</div>
					</div>
				</div>
			</v-col>
			<v-col cols="4" sm="3" class="py-0" v-if="posProfile.posa_input_qty">
				<v-text-field
					variant="solo"
					color="primary"
					class="pos-themed-input header-qty-input--hero"
					:label="frappe._('QTY')"
					hide-details
					data-pos-keyboard-target="item-qty"
					:model-value="qtyInput"
					@update:model-value="$emit('update:qtyInput', $event)"
					type="text"
					inputmode="decimal"
					@keydown.enter="$emit('enter')"
					@keydown.esc="blurTarget"
					@focus="$emit('clear-qty')"
					@click="$emit('clear-qty')"
					@blur="$emit('blur-qty')"
				></v-text-field>
			</v-col>
		</v-row>
		<v-expand-transition>
			<div v-if="toolsOpen" class="tools-panel">
				<div class="tools-panel__actions">
					<v-btn
						v-if="context === 'purchase'"
						density="compact"
						variant="text"
						color="primary"
						prepend-icon="mdi-plus"
						@click="$emit('open-new-item')"
						class="settings-btn"
					>
						{{ __("New Item") }}
					</v-btn>
					<v-btn
						density="compact"
						variant="text"
						color="primary"
						prepend-icon="mdi-cog-outline"
						@click="$emit('toggle-settings')"
						class="settings-btn"
					>
						{{ __("Settings") }}
					</v-btn>
					<v-btn
						density="compact"
						variant="text"
						color="primary"
						prepend-icon="mdi-refresh"
						@click="$emit('reload-items')"
						class="settings-btn"
					>
						{{ __("Reload Items") }}
					</v-btn>
				</div>
				<div class="tools-panel__meta">
					<span v-if="syncStatus" class="text-caption text-info font-weight-bold sync-status-label">
						{{ syncStatus }}
					</span>
					<span
						v-else-if="enableBackgroundSync"
						class="text-caption text-medium-emphasis last-sync-label"
					>
						{{ __("Last sync:") }} {{ lastSyncTime }}
					</span>
				</div>
			</div>
		</v-expand-transition>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const syncSearchCombobox = (root, state) => {
	const input = root?.matches?.("input") ? root : root?.querySelector?.("input");
	if (!input) return;
	const attributes = [
		"role",
		"aria-label",
		"aria-autocomplete",
		"aria-expanded",
		"aria-controls",
		"aria-activedescendant",
	];
	if (!state?.enabled) {
		attributes.forEach((attribute) => input.removeAttribute(attribute));
		return;
	}
	input.setAttribute("role", "combobox");
	input.setAttribute("aria-label", state.label || "Search saleable items");
	input.setAttribute("aria-autocomplete", "list");
	input.setAttribute("aria-expanded", String(Boolean(state.expanded)));
	if (state.controls) input.setAttribute("aria-controls", state.controls);
	else input.removeAttribute("aria-controls");
	if (state.activeDescendant) {
		input.setAttribute("aria-activedescendant", state.activeDescendant);
	} else {
		input.removeAttribute("aria-activedescendant");
	}
};

const vSearchCombobox = {
	mounted: (element, binding) => syncSearchCombobox(element, binding.value),
	updated: (element, binding) => syncSearchCombobox(element, binding.value),
};

const props = defineProps({
	searchInput: { type: String, default: "" },
	qtyInput: { type: [String, Number], default: 1 },
	posProfile: { type: Object, required: true },
	scannerLocked: { type: Boolean, default: false },
	enableBackgroundSync: { type: Boolean, default: false },
	lastSyncTime: { type: String, default: "" },
	syncStatus: { type: String, default: "" },
	showSyncProgress: { type: Boolean, default: false },
	syncProgress: { type: Number, default: 0 },
	syncItemsCount: { type: Number, default: 0 },
	context: { type: String, default: "pos" },
	searchCombobox: { type: Boolean, default: false },
	searchExpanded: { type: Boolean, default: false },
	searchControls: { type: String, default: "" },
	searchActiveDescendant: { type: String, default: "" },
});

const emit = defineEmits([
	"update:searchInput",
	"update:qtyInput",
	"esc",
	"enter",
	"search-keydown",
	"clear-search",
	"search-input",
	"search-paste",
	"focus",
	"clear-qty",
	"blur-qty",
	"start-camera",
	"open-new-item",
	"toggle-settings",
	"reload-items",
]);

const debounce_search = ref(null);
const toolsOpen = ref(false);
const clampedSyncProgress = computed(() => {
	const normalized = Number(props.syncProgress);
	if (!Number.isFinite(normalized) || normalized <= 0) {
		return 0;
	}
	return Math.min(100, Math.round(normalized));
});
const normalizedSyncItemsCount = computed(() => {
	const normalized = Number(props.syncItemsCount);
	if (!Number.isFinite(normalized) || normalized <= 0) {
		return 0;
	}
	return Math.round(normalized);
});
const translate = (value) => (typeof globalThis.__ === "function" ? globalThis.__(value) : value);
const syncItemsCountLabel = computed(() => {
	const count = normalizedSyncItemsCount.value;
	const itemLabel = count === 1 ? translate("item synced") : translate("items synced");
	return `${count.toLocaleString()} ${itemLabel}`;
});

const blurTarget = (event) => {
	event?.target?.blur?.();
};

const handleSearchEscape = (event) => {
	if (props.searchInput) {
		emit("esc");
		return;
	}
	blurTarget(event);
};

const handleSearchKeydown = (event) => {
	if (event?.__posaSearchKeyHandled) {
		return;
	}
	if (event?.key === "Escape") {
		handleSearchEscape(event);
		return;
	}
	if (event?.key === "Enter") {
		if (typeof event.preventDefault === "function") {
			event.preventDefault();
		}
		emit("enter", event);
		return;
	}
	emit("search-keydown", event);
};

const handleSearchKeydownCapture = (event) => {
	if (event?.key !== "ArrowDown" && event?.key !== "ArrowUp") {
		return;
	}
	event.__posaSearchKeyHandled = true;
	emit("search-keydown", event);
};

defineExpose({
	debounce_search,
});
</script>

<style scoped>
.sticky-header {
	position: sticky;
	top: 0;
	z-index: 5;
	background: var(--pos-surface);
	padding: 12px;
	border-bottom: 1px solid var(--pos-border);
	margin-bottom: 0;
}

.items {
	margin: 0;
}

.search-field-shell {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.search-sync-progress {
	display: flex;
	flex-direction: column;
	gap: 4px;
	padding: 0 6px 2px;
	animation: sync-progress-fade-in 160ms ease-out;
}

:deep(.search-sync-progress .v-progress-linear) {
	border-radius: 999px;
	overflow: hidden;
	box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}

.search-sync-progress__meta {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
}

.search-sync-progress__label,
.search-sync-progress__value {
	font-size: 0.7rem;
	line-height: 1.2;
	color: var(--pos-primary-variant);
}

.search-sync-progress__label {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	flex-wrap: wrap;
	font-weight: 600;
	letter-spacing: 0.01em;
}

.search-sync-progress__count {
	font-variant-numeric: tabular-nums;
	font-weight: 700;
	opacity: 0.82;
}

.search-sync-progress__value {
	font-variant-numeric: tabular-nums;
	font-weight: 700;
}

.tools-panel {
	margin-top: 8px;
	padding: 10px 12px;
	border-radius: 16px;
	background: var(--pos-surface-muted);
	border: 1px solid var(--pos-border);
}

.tools-panel__actions {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 6px;
}

.tools-panel__meta {
	display: flex;
	align-items: center;
	justify-content: flex-end;
	padding-top: 6px;
}

.settings-btn {
	text-transform: none !important;
	letter-spacing: normal !important;
	font-weight: 500 !important;
	background-color: transparent !important;
	min-height: 40px !important;
}

.last-sync-label {
	white-space: nowrap;
	font-size: 0.75rem;
}

.dynamic-margin-xs {
	margin-top: 4px;
}

:deep(.sticky-header .v-field) {
	border-radius: 16px;
}

.search-field-shell :deep(.v-label),
.search-field-shell :deep(.v-field-label) {
	color: var(--pos-primary-variant) !important;
	opacity: 1;
}

/* Hero Product Search Input (84px height, vertically centered) */
.search-field-shell :deep(.v-input) {
	--v-input-control-height: 84px !important;
}

.search-field-shell :deep(.v-field) {
	min-height: 84px !important;
	height: 84px !important;
	--v-input-control-height: 84px !important;
	--v-field-padding-top: 0px !important;
	--v-field-padding-bottom: 0px !important;
	--v-field-input-padding-top: 0px !important;
	--v-field-input-padding-bottom: 0px !important;
	padding: 0 18px !important;
	border-radius: 16px !important;
	box-shadow: 0 3px 12px rgba(0, 0, 0, 0.06) !important;
	display: flex !important;
	align-items: center !important;
}

.search-field-shell :deep(.v-field__field) {
	height: 100% !important;
	min-height: 84px !important;
	display: flex !important;
	align-items: center !important;
	align-self: center !important;
	padding: 0 !important;
	margin: 0 !important;
}

.search-field-shell :deep(.v-field__input) {
	height: 100% !important;
	display: flex !important;
	align-items: center !important;
	padding: 0 !important;
	margin: 0 !important;
}

.search-field-shell :deep(.v-field__input input),
.search-field-shell :deep(input) {
	height: 52px !important;
	line-height: normal !important;
	font-size: 2.2rem !important;
	font-weight: 700 !important;
	color: var(--pos-text-primary) !important;
	padding: 0 !important;
	margin: 0 !important;
	align-self: center !important;
	box-sizing: border-box !important;
}

.search-field-shell :deep(input::placeholder) {
	font-size: 1.8rem !important;
	font-weight: 500 !important;
	color: var(--pos-primary-variant) !important;
	opacity: 0.8 !important;
	line-height: normal !important;
	vertical-align: middle !important;
}

/* Ensure no label overlaps the typed input */
.search-field-shell :deep(.v-label),
.search-field-shell :deep(.v-field-label) {
	display: none !important;
}

.search-field-shell :deep(.v-field__prepend-inner) {
	align-self: center !important;
	padding: 0 !important;
	margin: 0 14px 0 0 !important;
	display: flex !important;
	align-items: center !important;
}

.search-field-shell :deep(.v-field__prepend-inner .v-icon) {
	font-size: 38px !important;
	width: 38px !important;
	height: 38px !important;
}

.search-field-shell :deep(.v-field__append-inner) {
	align-self: center !important;
	padding: 0 !important;
	margin: 0 !important;
	display: flex !important;
	align-items: center !important;
	gap: 8px !important;
}

.search-field-shell :deep(.v-field__clearable) {
	align-self: center !important;
	padding: 0 !important;
	margin: 0 !important;
	display: flex !important;
	align-items: center !important;
}

.search-field-shell :deep(.v-field__clearable .v-icon) {
	font-size: 30px !important;
	width: 30px !important;
	height: 30px !important;
}

.search-field-shell :deep(.v-field__append-inner .v-btn) {
	width: 46px !important;
	height: 46px !important;
	align-self: center !important;
}

.search-field-shell :deep(.v-field__append-inner .v-btn .v-icon) {
	font-size: 28px !important;
}

/* Matching 84px QTY input (if enabled) */
.header-qty-input--hero :deep(.v-field) {
	min-height: 84px !important;
	height: 84px !important;
	--v-input-control-height: 84px !important;
	border-radius: 16px !important;
	box-shadow: 0 3px 12px rgba(0, 0, 0, 0.06) !important;
}

.header-qty-input--hero :deep(.v-field__field) {
	height: 84px !important;
	min-height: 84px !important;
	align-items: center !important;
}

.header-qty-input--hero :deep(.v-field__input),
.header-qty-input--hero :deep(.v-field__input input),
.header-qty-input--hero :deep(input) {
	min-height: 84px !important;
	height: 84px !important;
	font-size: 2.2rem !important;
	line-height: 84px !important;
	font-weight: 700 !important;
	text-align: center;
	padding-top: 0 !important;
	padding-bottom: 0 !important;
}

.header-qty-input--hero :deep(.v-label.v-field-label),
.header-qty-input--hero :deep(input::placeholder) {
	font-size: 1.65rem !important;
	line-height: 1.2 !important;
	text-align: center;
	width: 100%;
}

@media (max-width: 768px) {
	.sticky-header {
		top: 0;
		z-index: 13;
		padding: 12px 12px 2px;
	}

	.tools-panel {
		padding: 8px 10px;
	}

	.tools-panel__meta {
		justify-content: flex-start;
	}

	.search-sync-progress {
		gap: 3px;
		padding: 0 2px 2px;
	}

	.search-sync-progress__label,
	.search-sync-progress__value {
		font-size: 0.68rem;
	}
}

@keyframes sync-progress-fade-in {
	from {
		opacity: 0;
		transform: translateY(-2px);
	}

	to {
		opacity: 1;
		transform: translateY(0);
	}
}
</style>
