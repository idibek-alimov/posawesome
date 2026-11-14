<template>
	<section class="purchase-history" :aria-label="__('История покупок')">
		<div class="purchase-filters">
			<v-text-field ref="searchInput" v-model="query" autofocus clearable hide-details variant="outlined" density="compact"
				class="purchase-search" :label="__('Телефон, имя, чек или ФД №')" prepend-inner-icon="mdi-magnify"
				@keydown.enter.prevent="refresh" />
			<v-text-field v-model="fromDate" type="date" :label="__('Покупки с')" hide-details variant="outlined" density="compact" />
			<v-text-field v-model="toDate" type="date" :label="__('Покупки по')" hide-details variant="outlined" density="compact" />
			<v-btn variant="text" :disabled="disabled" @click="today">{{ __('Сегодня') }}</v-btn>
		</div>
		<p class="text-caption text-medium-emphasis my-2">{{ __('Покупки на доступных вам кассах, сначала новые') }}</p>
		<v-alert v-if="error" type="warning" variant="tonal" class="mb-2">{{ error }}</v-alert>
		<v-progress-linear v-if="loading" indeterminate :aria-label="__('Loading')" />
		<p v-if="!loading && !error && !sales.length" class="py-4 text-medium-emphasis" role="status">{{ __('Покупки не найдены. Проверьте поиск и даты.') }}</p>
		<div class="purchase-list" :aria-busy="loading">
			<v-card v-for="sale in sales" :key="key(sale)" variant="outlined" class="purchase-row">
				<div class="purchase-summary">
					<div class="purchase-identity"><strong>{{ dateTime(sale) }}</strong><div class="text-caption">{{ sale.name }}</div></div>
					<div class="purchase-customer"><strong>{{ sale.customer_name || __('Покупатель без регистрации') }}</strong><div class="text-caption">{{ sale.customer_phone || '—' }}</div></div>
					<div class="purchase-amount"><strong>{{ money(sale.rounded_total || sale.grand_total) }} {{ sale.currency }}</strong><div class="text-caption">{{ sale.pos_profile }}<span v-if="sale.custom_fiscal_fd_number"> · ФД № {{ sale.custom_fiscal_fd_number }}</span></div></div>
					<div class="purchase-actions">
						<v-btn size="small" variant="text" :disabled="disabled || loading" :aria-expanded="detailKey === key(sale)" @click="toggleDetails(sale)">{{ __('Товары') }}</v-btn>
						<v-btn size="small" variant="tonal" :prepend-icon="actionIcon" :disabled="disabled || loading" @click="$emit('select', sale)">{{ actionLabel }}</v-btn>
					</div>
				</div>
				<div v-if="detailKey === key(sale)" class="purchase-details">
					<v-progress-linear v-if="detailLoading" indeterminate />
					<v-alert v-if="detailError" type="warning" variant="tonal">{{ detailError }}</v-alert>
					<v-table v-if="details" density="compact" class="purchase-desktop-items">
						<thead><tr><th>{{ __('Товар') }}</th><th>{{ __('Кол-во') }}</th><th>{{ __('Цена') }}</th><th>{{ __('Сумма') }}</th></tr></thead>
						<tbody><tr v-for="(item, index) in details.items" :key="index"><td>{{ item.item_code }} · {{ item.item_name }}</td><td>{{ item.qty }} {{ item.uom }}</td><td>{{ money(item.rate) }}</td><td>{{ money(item.amount) }}</td></tr></tbody>
					</v-table>
					<div v-if="details" class="purchase-mobile-items">
						<div v-for="(item, index) in details.items" :key="index" class="purchase-mobile-item">
							<div>{{ item.item_code }} · {{ item.item_name }}</div>
							<div class="purchase-item-amounts text-caption"><span>{{ item.qty }} {{ item.uom }} × {{ money(item.rate) }}</span><strong>{{ money(item.amount) }}</strong></div>
						</div>
					</div>
				</div>
			</v-card>
		</div>
		<div class="purchase-pagination mt-3">
			<v-btn variant="text" :disabled="loading || disabled || start === 0" @click="page(-1)">{{ __('Назад') }}</v-btn>
			<span v-if="sales.length" class="text-caption">{{ start + 1 }}–{{ start + sales.length }}</span>
			<v-btn variant="text" :disabled="loading || disabled || !hasMore" @click="page(1)">{{ __('Далее') }}</v-btn>
		</div>
	</section>
</template>

<script>
import { isManualOffline } from "../../../../offline/index";

const currentDate = () => {
	const today = new Date();
	return window.frappe?.datetime?.get_today?.() || `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
};

export default {
	props: {
		profile: { type: Object, required: true },
		actionLabel: { type: String, required: true },
		actionIcon: { type: String, default: "mdi-check" },
		disabled: Boolean,
	},
	emits: ["select"],
	data: () => ({ query: "", fromDate: currentDate(), toDate: currentDate(), sales: [], loading: false, error: "",
		start: 0, pageLength: 20, hasMore: false, generation: 0, timer: null, detailKey: "", detailLoading: false, details: null, detailError: "", detailGeneration: 0 }),
	watch: {
		query: "scheduleSearch", fromDate: "scheduleSearch", toDate: "scheduleSearch",
		"profile.name"() { this.refresh(); },
	},
	mounted() { this.refresh(); },
	beforeUnmount() { clearTimeout(this.timer); this.generation++; this.detailGeneration++; },
	methods: {
		key(sale) { return `${sale.doctype}:${sale.name}`; },
		money(value) { return Number(value || 0).toFixed(2); },
		dateTime(sale) { return `${String(sale.posting_date).replace(/^(\d{4})-(\d{2})-(\d{2})$/, '$3.$2.$1')} ${String(sale.posting_time || '').split(':').slice(0, 2).map(p => p.padStart(2, '0')).join(':')}`; },
		today() { this.fromDate = currentDate(); this.toDate = currentDate(); this.refresh(); },
		scheduleSearch() {
			// Invalidate immediately, including requests in flight during debounce.
			this.generation++; this.sales = []; this.hasMore = false; this.start = 0;
			this.detailKey = ""; this.detailGeneration++;
			clearTimeout(this.timer); this.timer = setTimeout(() => this.refresh(), 300);
		},
		refresh() { clearTimeout(this.timer); this.start = 0; return this.load(); },
		page(direction) { this.start = Math.max(0, this.start + direction * this.pageLength); return this.load(); },
		async load() {
			const generation = ++this.generation;
			this.detailGeneration++; this.detailKey = ""; this.details = null;
			this.sales = []; this.hasMore = false; this.error = ""; this.loading = true;
			try {
				// The health probe may still be checking (or stale) while read RPCs
				// already work. Respect explicit offline mode, then let this read
				// establish its own result. Posting retains its stricter guards.
				if (isManualOffline() || !navigator.onLine) throw new Error(__("Для истории покупок требуется соединение с ERPNext"));
				if (!this.fromDate || !this.toDate || this.fromDate > this.toDate) throw new Error(__("Укажите правильный период покупок"));
				const { message } = await frappe.call("posawesome.posawesome.api.market_checkout.purchase_history", {
					pos_profile: this.profile.name, query: this.query || "", from_date: this.fromDate, to_date: this.toDate, start: this.start, page_length: this.pageLength,
				});
				if (generation !== this.generation) return;
				this.sales = message.items; this.hasMore = message.has_more;
			} catch (error) { if (generation === this.generation) this.error = error.message; }
			finally { if (generation === this.generation) this.loading = false; }
		},
		async toggleDetails(sale) {
			const generation = ++this.detailGeneration;
			if (this.detailKey === this.key(sale)) { this.detailKey = ""; return; }
			this.detailKey = this.key(sale); this.details = null; this.detailError = ""; this.detailLoading = true;
			try {
				const { message } = await frappe.call("posawesome.posawesome.api.market_checkout.receipt_data", { invoice_name: sale.name, doctype: sale.doctype });
				if (generation === this.detailGeneration) this.details = message;
			} catch (error) { if (generation === this.detailGeneration) this.detailError = error.message; }
			finally { if (generation === this.detailGeneration) this.detailLoading = false; }
		},
	},
};
</script>

<style scoped>
.purchase-filters{display:grid;grid-template-columns:minmax(240px,1fr) 155px 155px auto;gap:10px;align-items:center}.purchase-list{display:grid;gap:8px}.purchase-row{border-color:rgba(var(--v-border-color),var(--v-border-opacity))}.purchase-summary{display:grid;grid-template-columns:minmax(140px,1fr) minmax(140px,1fr) minmax(140px,1fr) auto;gap:12px;padding:12px;align-items:center}.purchase-identity,.purchase-customer,.purchase-amount{min-width:0;overflow-wrap:anywhere}.purchase-actions{display:flex;gap:4px;align-items:center}.purchase-details{border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity));padding:8px 12px}.purchase-pagination{display:flex;align-items:center;justify-content:center;gap:12px}.purchase-mobile-items{display:none}.purchase-mobile-item{padding:8px;overflow-wrap:anywhere}.purchase-item-amounts{display:flex;justify-content:space-between;gap:10px;margin-top:6px;flex-wrap:wrap}.purchase-item-amounts strong{white-space:nowrap}
@media(max-width:960px){.purchase-filters{grid-template-columns:1fr 1fr auto}.purchase-search{grid-column:1/-1}.purchase-summary{grid-template-columns:1fr 1fr}.purchase-actions{justify-content:flex-end}}@media(max-width:500px){.purchase-filters{grid-template-columns:1fr 1fr}.purchase-filters>.v-btn{grid-column:1/-1;justify-self:end}.purchase-summary{gap:8px;padding:10px}.purchase-amount{grid-column:1/-1}.purchase-actions{grid-column:1/-1}.purchase-details{padding:4px}}
@media(max-width:600px){.purchase-desktop-items{display:none}.purchase-mobile-items{display:grid}}
</style>
