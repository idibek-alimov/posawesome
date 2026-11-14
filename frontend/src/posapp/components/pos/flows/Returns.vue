<template>
	<v-dialog v-model="open" max-width="1100" scrollable :persistent="busy">
		<v-card class="quick-returns">
			<v-card-title class="d-flex align-center">{{ __("Возврат") }}<v-spacer /><v-btn icon="mdi-close" variant="text" :disabled="busy" :aria-label="__('Close')" @click="open = false" /></v-card-title>
			<v-card-text>
				<v-alert v-if="error" type="warning" variant="tonal" class="mb-3">{{ error }}</v-alert>
				<v-alert v-if="pending" type="info" variant="tonal" class="mb-3">{{ __("Результат возврата не подтверждён. Восстановите эту операцию перед новым возвратом.") }}</v-alert>
				<template v-if="!completed && !pending">
					<div class="mb-3"><v-btn v-if="scenario !== 'guest'" variant="text" :disabled="busy" @click="scenario = 'guest'">{{ __("Возврат без чека") }}</v-btn><v-btn v-else variant="text" :disabled="busy" prepend-icon="mdi-arrow-left" @click="scenario = 'receipt'">{{ __("История покупок") }}</v-btn></div>
					<PurchaseHistory v-if="open && scenario !== 'guest'" v-show="!source" :profile="profile" :disabled="busy" :action-label="__('Выбрать')" @select="loadSale" />
					<v-text-field v-if="scenario === 'guest'" ref="searchInput" v-model="query" autofocus clearable hide-details density="compact" variant="outlined" :disabled="busy"
						:label="__('Штрихкод или код товара')" @keydown.enter.prevent="search" append-inner-icon="mdi-magnify" @click:append-inner="search" />
					<v-progress-linear v-if="busy" indeterminate class="mt-2" />
					<div v-if="source" class="mt-3 d-flex align-center"><b>{{ source.name }} · {{ source.customer_name }}</b><v-spacer /><v-btn size="small" @click="source = null; rows = []">{{ __("Другой чек") }}</v-btn></div>
					<v-table v-if="rows.length" density="compact" class="return-items mt-3">
						<thead><tr><th>{{ __("Вернуть") }}</th><th>{{ __("Товар") }}</th><th>{{ __("Кол-во") }}</th><th>{{ __("Цена") }}</th></tr></thead>
						<tbody><tr v-for="(row, index) in rows" :key="row.name || row.item_code">
							<td><v-checkbox-btn v-model="row.selected" :aria-label="`${__('Return')} ${row.item_name}`" /></td>
							<td>{{ row.item_code }}<br>{{ row.item_name }}</td>
							<td><v-text-field v-model.number="row.returnQty" type="number" min="0.001" :max="scenario === 'guest' ? undefined : row.qty" step="any" density="compact" hide-details :aria-label="`${__('Quantity')} ${index + 1}`" /></td>
							<td class="text-no-wrap">{{ money(row.rate) }}</td>
						</tr></tbody>
					</v-table>
					<v-btn v-if="rows.some(r => r.batch_no || r.serial_no || r.has_batch_no || r.has_serial_no)" class="mt-3" variant="text" @click="openDetailedReturn">{{ __("Уточнить партии / серийные номера") }}</v-btn>
					<div v-if="rows.length" class="return-options mt-3">
						<v-select v-model="refundType" :items="refundMethods" item-title="label" item-value="value" :label="__('Вернуть')" hide-details density="compact" variant="outlined" />
						<v-select v-model="mode" :items="receiptModes" item-title="label" item-value="value" :label="__('Чек')" hide-details density="compact" variant="outlined" />
					</div>
				</template>
				<template v-if="completed"><p>{{ __("Возврат сохранён") }}: <b>{{ completed.name }}</b></p><v-btn class="mt-3" prepend-icon="mdi-printer" @click="printSale(completed)">{{ __("Товарный чек") }}</v-btn></template>
			</v-card-text>
			<v-card-actions><v-btn :disabled="busy" @click="open = false">{{ __("Закрыть") }}</v-btn><v-spacer />
				<v-btn v-if="!completed" color="primary" variant="flat" :loading="busy" :disabled="isOffline() || (!pending && !rows.some(r => r.selected))" @click="refund">{{ __(pending ? "Восстановить возврат" : "Вернуть деньги") }}</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>
<script>
import PurchaseHistory from "./PurchaseHistory.vue";
import { useUIStore } from "../../../stores/uiStore";
import { printMarketReceipt } from "../../../services/marketReceipt";
import { useFiscalPrinter } from "../../../composables/pos/payments/useFiscalPrinter";
import stockCoordinator from "../../../utils/stockCoordinator";
import { isOffline, updateLocalStock } from "../../../../offline/index";

export default {
	components: { PurchaseHistory },
	setup() { return { uiStore: useUIStore(), fiscal: useFiscalPrinter(), isOffline }; },
	data: () => ({ open: false, busy: false, query: "", scenario: "receipt", source: null, rows: [], refundType: "cash", mode: "none", error: "", completed: null, pending: null, generation: 0 }),
	computed: {
		profile() { return this.uiStore.posProfile || {}; },
		refundMethods() { return [{ value: "cash", label: __("Наличными") }, ...(this.source?.customer && this.source.customer !== this.profile.customer ? [{ value: "credit", label: __("На баланс клиента") }] : [])]; },
		receiptModes() { return [{ value: "none", label: __("Без чека") }, { value: "receipt", label: __("Товарный чек") }, ...(this.refundType !== "credit" ? [{ value: "fiscal", label: __("Фискальный чек") }] : [])]; },
		pendingKey() { return `posa-quick-return:${this.profile.name}`; },
	},
	watch: {
		scenario() { this.generation++; this.query = ""; this.source = null; this.rows = []; this.refundType = "cash"; this.error = ""; },
		refundType(value) { if (value === "credit" && this.mode === "fiscal") this.mode = "none"; },
	},
	methods: {
		money(value) { return Math.abs(Number(value || 0)).toFixed(2); },
		async call(method, args) { return (await frappe.call(`posawesome.posawesome.api.market_checkout.${method}`, args)).message; },
		async search() {
			if (this.busy || this.scenario !== "guest" || !this.query?.trim()) return;
			const generation = ++this.generation;
			this.busy = true; this.error = "";
			try {
				const row = await this.call("guest_item", { pos_profile: this.profile.name, code: this.query });
				if (generation !== this.generation) return;
				const existing = this.rows.find(r => r.item_code === row.item_code);
				if (existing) existing.returnQty++;
				else this.rows.push({ ...row, rate: row.rate || row.price_list_rate, selected: true, returnQty: 1 });
				this.query = "";
			} catch (error) { this.error = error.message; }
			finally { this.busy = false; }
		},
		async loadSale(sale) {
			const generation = ++this.generation;
			this.busy = true; this.error = "";
			try {
				const result = await this.call("return_items", { invoice_name: sale.name, doctype: sale.doctype, pos_profile: this.profile.name });
				if (generation !== this.generation || !this.open) return;
				this.source = { ...result, doctype: sale.doctype };
				this.rows = result.items.map(row => ({ ...row, selected: false, returnQty: row.qty }));
				if (!this.rows.length) this.error = __("Все товары уже возвращены");
			} catch (error) { this.error = error.message; }
			finally { this.busy = false; }
		},
		openDetailedReturn() {
			const selected = this.rows.filter(row => row.selected);
			if (!selected.length) { this.error = __("Select returned items"); return; }
			const invoice_doc = {
				is_return: 1, customer: this.source?.customer || this.profile.customer,
				return_against: this.source?.name, company: this.profile.company, pos_profile: this.profile.name,
				update_stock: 1, discount_amount: this.source?.discount_amount || 0,
				additional_discount_percentage: this.source?.additional_discount_percentage || 0,
				items: selected.map(row => {
					const item = { ...row, qty: -Math.abs(Number(row.returnQty)), amount: -Math.abs(Number(row.returnQty) * Number(row.rate)), warehouse: this.profile.warehouse };
					if (this.source) item[this.source.doctype === "POS Invoice" ? "pos_invoice_item" : "sales_invoice_item"] = row.name;
					delete item.name; delete item.selected; delete item.returnQty;
					return item;
				}),
			};
			this.eventBus.emit("load_return_invoice", { invoice_doc, return_doc: this.source });
			this.open = false;
		},
		async printSale(sale) { try { await printMarketReceipt(sale, this.profile); } catch (error) { this.error = error.message; } },
		async refund() {
			if (this.busy || isOffline()) return;
			this.busy = true; this.error = "";
			try {
				const selected = this.rows.filter(r => r.selected);
				if (!this.pending && selected.some(r => !Number.isFinite(Number(r.returnQty)) || r.returnQty <= 0 || (this.scenario !== "guest" && r.returnQty > r.qty))) throw new Error(__("Проверьте количество возвращаемых товаров"));
				const request = this.pending || { pos_profile: this.profile.name, opening_shift: this.uiStore.posOpeningShift?.name,
					selected_items: selected.map(r => ({ name: r.name, item_code: r.item_code, qty: r.returnQty })), request_id: crypto.randomUUID(),
					invoice_name: this.source?.name, doctype: this.source?.doctype || "Sales Invoice", as_credit: this.refundType === "credit" ? 1 : 0 };
				const finishingMode = this.pending?.finishingMode || this.mode;
				this.pending = { ...request, finishingMode };
				localStorage.setItem(this.pendingKey, JSON.stringify(this.pending));
				const { finishingMode: _ignored, ...args } = this.pending;
				const result = await this.call("refund", args);
				if (Number(result.docstatus) !== 1) throw new Error(__("Возврат ещё не проведён. Восстановите результат."));
				this.completed = result;
				localStorage.removeItem(this.pendingKey); this.pending = null;
				this.uiStore.setLastInvoice(result.name, result.doctype);
				if (result.update_stock) {
					updateLocalStock(result.items || []);
					stockCoordinator.applyInvoiceConsumption(result.items || [], { source: "invoice" });
					this.uiStore.setLastStockAdjustment({ items: result.items, item_codes: (result.items || []).map(r => r.item_code), timestamp: Date.now() });
				}
				if (finishingMode === "receipt") await this.printSale(result);
				if (finishingMode === "fiscal") {
					const fiscal = await this.fiscal.printFiscalReceipt(result);
					if (!fiscal.success) this.error = fiscal.error + " · " + __("Восстановите ФД из списка счетов.");
				}
			} catch (error) {
				this.error = error.message;
				if (error.status >= 400 && error.status < 500) {
					localStorage.removeItem(this.pendingKey); this.pending = null;
				}
			}
			finally { this.busy = false; }
		},
		openReturns() {
			this.generation++; this.scenario = "receipt"; this.query = ""; this.source = null; this.rows = []; this.completed = null; this.error = ""; this.mode = "none"; this.refundType = "cash";
			try { this.pending = JSON.parse(localStorage.getItem(this.pendingKey) || "null"); } catch { this.pending = null; }
			this.open = true;
			if (isOffline()) this.error = __("Для возврата требуется соединение с ERPNext");
		},
	},
	created() { this.eventBus.on("open_returns", this.openReturns); },
	beforeUnmount() { this.eventBus.off("open_returns", this.openReturns); },
};
</script>
<style scoped>
.return-scenarios{display:flex;flex-wrap:wrap;height:auto;gap:4px}.return-options{display:grid;grid-template-columns:1fr 1fr;gap:12px}.return-items td{padding-top:6px!important;padding-bottom:6px!important}.return-items :deep(.v-input){min-width:80px;max-width:110px}.quick-returns :deep(.v-card-title){white-space:normal}@media(max-width:600px){.return-options{grid-template-columns:1fr}.quick-returns :deep(.v-card-text){padding:12px}.return-scenarios :deep(.v-btn){font-size:12px}}
</style>
