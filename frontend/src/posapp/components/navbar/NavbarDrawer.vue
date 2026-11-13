<template>
	<v-navigation-drawer
		v-model="drawerOpen"
		:rail="mini"
		expand-on-hover
		width="260"
		:class="['drawer-custom', { 'drawer-visible': drawerOpen }, rtlClasses]"
		@mouseleave="handleMouseLeave"
		temporary
		:location="isRtl ? 'right' : 'left'"
		:scrim="scrimColor"
	>
		<div class="drawer-shell">
			<div>
				<div v-if="!mini" class="drawer-header">
					<v-avatar size="40">
						<v-img :src="companyImg" alt="Company logo" />
					</v-avatar>
					<span class="drawer-company">{{ company }}</span>
				</div>
				<div v-else class="drawer-header-mini">
					<v-avatar size="40">
						<v-img :src="companyImg" alt="Company logo" />
					</v-avatar>
				</div>

				<v-divider />

				<!-- Primary Flagship Actions: POS and Expense (prominent, bold, larger font) -->
				<div class="drawer-primary-section">
					<v-list density="default" nav class="drawer-list-primary">
						<v-list-item
							v-for="(item, index) in primaryItems"
							:key="item.to || item.text"
							:value="item.to || index"
							:to="item.to"
							@click="handleItemClick"
							class="drawer-item drawer-item--primary"
							active-class="active-item"
							:data-test="`drawer-item-${item.to ? item.to.replace('/', '') : index}`"
						>
							<template v-slot:prepend>
								<div class="drawer-icon-wrap drawer-icon-wrap--primary">
									<v-icon class="drawer-icon drawer-icon--primary">{{ item.icon }}</v-icon>
								</div>
							</template>
							<v-list-item-title class="drawer-item-title drawer-item-title--primary">
								{{ item.text }}
							</v-list-item-title>
						</v-list-item>
					</v-list>
				</div>

				<!-- Collapsible Secondary Items (hidden by default) -->
				<div v-if="secondaryItems.length" class="drawer-secondary-section">
					<button
						type="button"
						class="drawer-more-btn"
						@click="toggleShowMore"
						:aria-expanded="showMore"
						data-test="drawer-more-toggle"
					>
						<div class="drawer-more-btn__content">
							<span class="drawer-more-btn__label">
								{{ showMore ? __('Show less') : __('More options') }}
							</span>
							<span v-if="!showMore" class="drawer-more-btn__count">
								{{ secondaryItems.length }}
							</span>
						</div>
						<v-icon size="18" class="drawer-more-btn__icon">
							{{ showMore ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
						</v-icon>
					</button>

					<v-expand-transition>
						<div
							v-show="showMore"
							class="drawer-secondary-collapse"
							data-test="drawer-secondary-collapse"
						>
							<v-list density="compact" nav class="drawer-list-secondary">
								<v-list-item
									v-for="(item, index) in secondaryItems"
									:key="item.to || item.text"
									:value="item.to || (primaryItems.length + index)"
									:to="item.to"
									@click="handleItemClick"
									class="drawer-item drawer-item--secondary"
									active-class="active-item"
									:data-test="`drawer-item-${item.to ? item.to.replace('/', '') : index}`"
								>
									<template v-slot:prepend>
										<v-icon class="drawer-icon drawer-icon--secondary">{{ item.icon }}</v-icon>
									</template>
									<v-list-item-title class="drawer-item-title drawer-item-title--secondary">
										{{ item.text }}
									</v-list-item-title>
								</v-list-item>
							</v-list>
						</div>
					</v-expand-transition>
				</div>
			</div>

			<div v-if="footerAction" class="drawer-footer" data-test="drawer-footer-settings">
				<v-divider class="drawer-footer-divider" />
				<button
					type="button"
					class="drawer-footer-action"
					data-test="drawer-footer-action"
					@click="handleFooterActionClick"
				>
					<span class="drawer-footer-action__icon">
						<v-icon class="drawer-icon">{{ footerAction.icon }}</v-icon>
					</span>
					<span v-if="!mini" class="drawer-footer-action__copy">
						<span class="drawer-footer-action__title">{{ footerAction.text }}</span>
						<span v-if="footerAction.subtitle" class="drawer-footer-action__subtitle">
							{{ footerAction.subtitle }}
						</span>
					</span>
				</button>
			</div>
		</div>
	</v-navigation-drawer>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useRtl } from "../../composables/core/useRtl";

defineOptions({
	name: "NavbarDrawer",
});

const props = defineProps({
	drawer: Boolean,
	company: String,
	companyImg: String,
	items: Array,
	item: Number,
	isDark: Boolean,
	footerAction: {
		type: Object,
		default: null,
	},
});

const emit = defineEmits(["update:drawer", "update:item", "open-settings"]);
const { isRtl, rtlClasses } = useRtl();

let route = null;
try {
	route = useRoute();
} catch {
	route = null;
}

const mini = ref(false);
const drawerOpen = ref(props.drawer);
const activeItem = ref(props.item);
const showMore = ref(false);
let closeTimeout = null;

function __(text, ...args) {
	if (typeof window !== "undefined" && typeof window.__ === "function") {
		return window.__(text, ...args);
	}
	return text;
}

const primaryItems = computed(() => {
	const list = props.items || [];
	return list.filter((item, index) => Boolean(item.primary || index < 2));
});

const secondaryItems = computed(() => {
	const list = props.items || [];
	return list.filter((item, index) => !item.primary && index >= 2);
});

// Auto-expand secondary items when current route is inside secondary items
watch(
	() => route?.path,
	(currentPath) => {
		if (currentPath && secondaryItems.value.some((item) => item.to === currentPath)) {
			showMore.value = true;
		}
	},
	{ immediate: true },
);

function toggleShowMore() {
	showMore.value = !showMore.value;
}

const scrimColor = computed(() => {
	// Use an opaque background in light mode so that
	// underlying content doesn't show through the drawer
	return props.isDark ? true : "rgba(255,255,255,1)";
});

watch(
	() => props.drawer,
	(val) => {
		drawerOpen.value = val;
		if (val) {
			mini.value = false;
		}
	},
);

watch(drawerOpen, (val) => {
	document.body.style.overflow = val ? "hidden" : "";
	emit("update:drawer", val);
});

watch(
	() => props.item,
	(val) => {
		activeItem.value = val;
	},
);

watch(activeItem, (val) => {
	emit("update:item", val);
});

function handleMouseLeave() {
	if (!drawerOpen.value) return;
	clearTimeout(closeTimeout);
	closeTimeout = setTimeout(() => {
		drawerOpen.value = false;
		mini.value = true;
	}, 250);
}

function handleItemClick() {
	// Close drawer after selection if mobile
	if (window.innerWidth < 1024) {
		closeDrawer();
	}
}

function handleFooterActionClick() {
	emit("open-settings");
	closeDrawer();
}

function closeDrawer() {
	drawerOpen.value = false;
	mini.value = true;
}
</script>

<style scoped>
/* Custom styling for the navigation drawer */
.drawer-custom {
	background-color: var(--surface-secondary, #ffffff);
	transition: var(--transition-normal, all 0.3s ease);
	z-index: 1005 !important; /* Higher than navbar but lower than dialogs */
}

.drawer-shell {
	height: 100%;
	display: flex;
	flex-direction: column;
	justify-content: space-between;
}

/* Styling for the header section of the expanded navigation drawer */
.drawer-header {
	display: flex;
	align-items: center;
	height: 64px;
	padding: 0 16px;
	background: linear-gradient(135deg, #f8f9fa 0%, #e3f2fd 100%);
	border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

/* Styling for the header section of the mini navigation drawer */
.drawer-header-mini {
	display: flex;
	justify-content: center;
	align-items: center;
	height: 64px;
	background: linear-gradient(135deg, #f8f9fa 0%, #e3f2fd 100%);
	border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

/* Styling for the company name text within the drawer header */
.drawer-company {
	margin-left: 12px;
	flex: 1;
	font-weight: 500;
	font-size: 1rem;
	color: #0097a7;
	font-family: "Roboto", sans-serif;
}

/* Primary Section (POS and Expenses) */
.drawer-primary-section {
	padding: 6px 6px 2px 6px;
}

.drawer-list-primary {
	padding: 0 !important;
}

.drawer-item--primary {
	min-height: 52px !important;
	border-radius: 12px !important;
	margin: 4px 4px 6px 4px !important;
	padding: 8px 12px !important;
	transition:
		background-color 0.18s ease,
		border-color 0.18s ease,
		transform 0.18s ease;
}

.drawer-item--primary:hover {
	background-color: rgba(25, 118, 210, 0.08) !important;
	transform: translateX(2px);
}

.drawer-icon-wrap--primary {
	width: 38px;
	height: 38px;
	border-radius: 10px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	background: rgba(25, 118, 210, 0.08);
	flex-shrink: 0;
	transition: background-color 0.2s ease;
}

.drawer-icon--primary {
	font-size: 24px !important;
	color: var(--pos-primary, #1976d2);
}

.drawer-item-title--primary {
	margin-left: 10px;
	font-weight: 700 !important;
	font-size: 1.15rem !important;
	line-height: 1.3;
	color: var(--pos-text-primary) !important;
	font-family: "Roboto", sans-serif;
	letter-spacing: 0.01em;
}

/* Secondary Collapsible Section */
.drawer-secondary-section {
	padding: 4px 10px 8px 10px;
}

.drawer-more-btn {
	width: 100%;
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 8px 12px;
	border-radius: 10px;
	border: 1px dashed var(--pos-border, rgba(0, 0, 0, 0.15));
	background: transparent;
	color: var(--pos-text-secondary, #666666);
	cursor: pointer;
	font-family: "Roboto", sans-serif;
	font-size: 0.85rem;
	font-weight: 600;
	transition: all 0.2s ease;
	margin-top: 4px;
	margin-bottom: 6px;
}

.drawer-more-btn:hover {
	background: rgba(25, 118, 210, 0.06);
	border-color: var(--pos-primary, #1976d2);
	color: var(--pos-primary, #1976d2);
}

.drawer-more-btn__content {
	display: flex;
	align-items: center;
	gap: 6px;
}

.drawer-more-btn__label {
	font-size: 0.85rem;
	font-weight: 600;
}

.drawer-more-btn__count {
	font-size: 0.72rem;
	font-weight: 700;
	padding: 1px 6px;
	border-radius: 10px;
	background: rgba(0, 0, 0, 0.06);
	color: var(--pos-text-secondary);
}

.drawer-more-btn__icon {
	color: inherit;
	transition: transform 0.2s ease;
}

.drawer-list-secondary {
	padding: 0 !important;
}

.drawer-item--secondary {
	min-height: 40px !important;
	border-radius: 8px !important;
	margin: 2px 0 !important;
	padding: 6px 10px !important;
}

.drawer-icon--secondary {
	font-size: 20px !important;
	color: var(--pos-text-secondary) !important;
}

.drawer-item-title--secondary {
	margin-left: 8px;
	font-size: 0.92rem !important;
	font-weight: 500 !important;
	color: var(--pos-text-primary) !important;
}

/* Hover effect for all list items in the navigation drawer */
.v-list-item:hover {
	background-color: rgba(25, 118, 210, 0.08) !important;
}

.drawer-footer {
	padding: 10px 12px 14px;
	display: grid;
	gap: 12px;
}

.drawer-footer-action {
	width: 100%;
	border: 1px solid var(--pos-border);
	border-radius: 16px;
	background: var(--pos-card-bg);
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 12px 14px;
	text-align: left;
	transition:
		transform 0.18s ease,
		border-color 0.18s ease,
		box-shadow 0.18s ease;
}

.drawer-footer-action:hover {
	transform: translateY(-1px);
	border-color: var(--pos-primary);
	box-shadow: 0 6px 16px var(--pos-shadow);
}

.drawer-footer-action__icon {
	width: 36px;
	height: 36px;
	border-radius: 12px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	background: linear-gradient(135deg, #1976d2 0%, #42a5f5 100%);
	flex-shrink: 0;
}

.drawer-footer-action__copy {
	display: grid;
	gap: 3px;
	min-width: 0;
}

.drawer-footer-action__title {
	font-size: 13px;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.drawer-footer-action__subtitle {
	font-size: 11px;
	line-height: 1.35;
	color: var(--pos-text-secondary);
}

/* Styling for the actively selected list item in the navigation drawer */
.active-item {
	background-color: rgba(25, 118, 210, 0.12) !important;
	border-right: 3px solid var(--pos-primary, #1976d2);
}

.active-item.drawer-item--primary .drawer-icon-wrap--primary {
	background: rgba(25, 118, 210, 0.18);
}

.rtl-drawer .active-item,
:deep(.rtl) .active-item,
[dir="rtl"] .active-item {
	border-right: none;
	border-left: 3px solid var(--pos-primary, #1976d2);
}

/* Theme-aware drawer styling */
.drawer-custom {
	background-color: var(--pos-navbar-bg) !important;
	color: var(--pos-text-primary) !important;
}

.drawer-header,
.drawer-header-mini {
	background: var(--pos-navbar-bg) !important;
	border-bottom: 1px solid var(--pos-border);
}

:deep([data-theme="dark"]) .drawer-item-title--primary,
:deep(.v-theme--dark) .drawer-item-title--primary {
	color: var(--pos-text-primary) !important;
	font-weight: 700 !important;
	font-size: 1.15rem !important;
	font-family: "Roboto", sans-serif;
}

:deep([data-theme="dark"]) .drawer-icon-wrap--primary,
:deep(.v-theme--dark) .drawer-icon-wrap--primary {
	background: rgba(144, 202, 249, 0.12);
}

:deep([data-theme="dark"]) .drawer-item--primary:hover,
:deep(.v-theme--dark) .drawer-item--primary:hover {
	background-color: rgba(144, 202, 249, 0.08) !important;
}

:deep([data-theme="dark"]) .active-item.drawer-item--primary .drawer-icon-wrap--primary,
:deep(.v-theme--dark) .active-item.drawer-item--primary .drawer-icon-wrap--primary {
	background: rgba(144, 202, 249, 0.22);
}

:deep([data-theme="dark"]) .drawer-more-btn,
:deep(.v-theme--dark) .drawer-more-btn {
	border-color: rgba(255, 255, 255, 0.18);
	color: rgba(255, 255, 255, 0.7);
}

:deep([data-theme="dark"]) .drawer-more-btn:hover,
:deep(.v-theme--dark) .drawer-more-btn:hover {
	background: rgba(144, 202, 249, 0.08);
	border-color: #90caf9;
	color: #90caf9;
}

:deep([data-theme="dark"]) .drawer-more-btn__count,
:deep(.v-theme--dark) .drawer-more-btn__count {
	background: rgba(255, 255, 255, 0.12);
	color: rgba(255, 255, 255, 0.7);
}

:deep([data-theme="dark"]) .drawer-item-title--secondary,
:deep(.v-theme--dark) .drawer-item-title--secondary {
	color: var(--pos-text-primary) !important;
	font-weight: 500;
	font-size: 0.92rem;
	font-family: "Roboto", sans-serif;
}

:deep([data-theme="dark"]) .drawer-icon--secondary,
:deep(.v-theme--dark) .drawer-icon--secondary {
	color: rgba(255, 255, 255, 0.7) !important;
	font-size: 20px;
}

:deep([data-theme="dark"]) .drawer-company,
:deep(.v-theme--dark) .drawer-company {
	color: var(--text-primary, #ffffff) !important;
	font-weight: 500;
	font-size: 1rem;
	font-family: "Roboto", sans-serif;
}

:deep([data-theme="dark"]) .drawer-icon,
:deep(.v-theme--dark) .drawer-icon {
	color: var(--pos-primary) !important;
	font-size: 24px;
}

:deep([data-theme="dark"]) .v-list-item:hover,
:deep(.v-theme--dark) .v-list-item:hover {
	background-color: rgba(144, 202, 249, 0.08) !important;
}

:deep([data-theme="dark"]) .active-item,
:deep(.v-theme--dark) .active-item {
	background-color: rgba(144, 202, 249, 0.12) !important;
	border-right: 3px solid #90caf9;
}

:deep([data-theme="dark"]) .v-divider,
:deep(.v-theme--dark) .v-divider {
	border-color: rgba(255, 255, 255, 0.12) !important;
}

/* Hide drawer by default, show only when activated */
.drawer-custom {
	display: none !important;
}
.drawer-custom.drawer-visible {
	display: block !important;
}

/* Responsive adjustments for width and dark theme */
@media (max-width: 900px) and (orientation: landscape) {
	.drawer-custom.drawer-visible {
		width: 200px !important;
	}
}

@media (min-width: 601px) and (max-width: 1024px) {
	.drawer-custom.drawer-visible {
		width: 250px !important;
	}
}

@media (min-width: 1025px) {
	.drawer-custom.drawer-visible {
		width: 300px !important;
	}
}

@media (max-width: 1024px) {
	.drawer-custom.drawer-visible {
		background-color: var(--pos-navbar-bg) !important;
	}
}
</style>
