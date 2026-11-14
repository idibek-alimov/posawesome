import JsBarcode from "jsbarcode";
import { printHtmlViaQz } from "./qzTray";
import { confirmDocumentPrintFallback, shouldUseConfiguredQzDocumentPrinting } from "./documentPrint";

declare const frappe: any;
const escape = (value: any) => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const money = (value: any) => Math.abs(Number(value || 0)).toFixed(2).replace(".", ",");
const quantity = (value: any) => Math.abs(Number(value || 0)).toFixed(6).replace(/0{1,3}$/, "");
const date = (value: any) => String(value || "").replace(/^(\d{4})-(\d{2})-(\d{2})$/, (_, y, m, d) => `${d}.${m}.${y.slice(-2)}`);

/** Store receipt only: firmware owns the official fiscal title, IDs and QR. */
export function renderMarketReceipt(doc: any, barcode = "") {
	const totals = doc.receipt_totals || { subtotal: doc.total ?? doc.grand_total, discount: doc.discount_amount, total: doc.rounded_total || doc.grand_total };
	const pair = (label: string, value: any, cls = "") => `<div class="pair ${cls}"><span class="label">${escape(label)}</span><span class="value">${escape(value)}</span></div>`;
	const amount = (label: string, value: any, cls = "") => pair(label, money(value), `amount ${cls}`);
	const payments = (doc.payments || []).filter((p: any) => Number(p.amount));
	const cash = payments.filter((p: any) => p.type === "Cash").reduce((sum: number, p: any) => sum + Math.abs(Number(p.amount)), 0);
	const noncash = payments.filter((p: any) => p.type === "Bank").reduce((sum: number, p: any) => sum + Math.abs(Number(p.amount)), 0);
	const other = payments.filter((p: any) => p.type !== "Cash" && p.type !== "Bank");
	const taxRows = (doc.taxes || []).filter((t: any) => Number(t.amount));
	return `<!doctype html><html lang="tg"><head><meta charset="utf-8"><title>${escape(doc.name)}</title><style>
	@page{size:80mm auto;margin:0}*{box-sizing:border-box}html,body{margin:0;padding:0;color:#000;background:#fff}
	body{width:80mm;padding:5mm 4mm;font:12px/1.2 "Courier New","DejaVu Sans Mono",monospace;font-variant-numeric:tabular-nums;font-weight:600}
	.header{text-align:center}.title{font-size:14px;font-weight:700;margin:3mm 0 4mm}.store{font-weight:700;margin:2mm 0}.address,.contacts{overflow-wrap:anywhere}.section{border-top:1px dashed #000;margin-top:2mm;padding-top:2mm}
	.pair{display:flex;justify-content:space-between;align-items:baseline;gap:2mm}.label{flex-shrink:0;max-width:65%}.value{text-align:right;overflow-wrap:anywhere;min-width:0}.amount .value{white-space:nowrap}
	.item{break-inside:avoid;margin-bottom:2mm}.name{overflow-wrap:anywhere}.article{font-size:11px}.calculation{display:flex;justify-content:space-between;gap:2mm}.calculation span:last-child{white-space:nowrap}.discount{text-align:right;font-size:11px}.grand{font-weight:700;font-size:14px}.tax-description{overflow-wrap:anywhere;font-size:11px}
	.barcode{margin:3mm 0 1mm;text-align:left}.barcode svg{display:block;max-width:100%;height:15mm}.invoice-id{font-size:10px;overflow-wrap:anywhere}.thanks{margin-top:2mm}.footer{border-bottom:1px dashed #000;padding-bottom:2mm}
	@media screen{body{margin:10px auto}}@media print{body{margin:0}}
	</style></head><body><header class="header"><div class="title">${doc.is_return ? "БАРГАРДОНИДАНИ МОЛ" : "РАСИДИ МОЛӢ"}</div><div class="store">${escape(doc.store_name || doc.company)}</div>
	${doc.address ? `<div class="address">${escape(doc.address)}</div>` : ""}${doc.contacts ? `<div class="contacts">${escape(doc.contacts)}</div>` : ""}</header>
	<section class="section meta">${doc.tax_id ? pair("РМА:", doc.tax_id) : ""}${pair("ХАЗИНАДОР:", doc.cashier)}${pair("КАССА №:", doc.register)}${pair("РАСИД №:", doc.name)}${pair("ТАЪРИХ:", `${date(doc.posting_date)} ${String(doc.posting_time || "").slice(0, 5)}`)}${pair("АМАЛИЁТ:", doc.is_return ? "БАРГАРДОНИДАН" : "ФУРӮШ")}${pair("АСЪОР:", doc.currency)}
	${doc.customer_name ? pair("ХАРИДОР:", doc.customer_name) : ""}</section>
	<section class="section items">${(doc.items || []).map((row: any) => `<div class="item"><div class="name">${escape(row.item_name || row.item_code)}</div>${row.item_code && row.item_code !== row.item_name ? `<div class="article">Артикул: ${escape(row.item_code)}</div>` : ""}<div class="calculation"><span>${money(row.rate)} × ${quantity(row.qty)}${row.uom ? ` ${escape(row.uom)}` : ""}</span><span>= ${money(row.amount)}</span></div>${Number(row.discount_amount) ? `<div class="discount">Тахфиф: ${money(Math.abs(Number(row.qty)) * Number(row.discount_amount))}</div>` : ""}</div>`).join("")}</section>
	<section class="section totals">${amount("ҶАМЪ:", totals.subtotal)}${amount("ТАХФИФ:", totals.discount)}</section>
	<section class="section payments">${amount("НАҚДӢ:", cash)}${amount("ҒАЙРИНАҚДӢ:", noncash)}${other.map((p: any) => amount(`${p.mode_of_payment}:`, p.amount)).join("")}${Number(doc.posa_redeemed_customer_credit) ? amount("АЗ ТАВОЗУНИ МУШТАРӢ:", doc.posa_redeemed_customer_credit) : ""}${Number(doc.loyalty_amount) ? amount("БО ХОЛҲО:", doc.loyalty_amount) : ""}${amount(doc.is_return ? "БАРГАРДОНИДА ШУД:" : "ПАРДОХТ ШУД:", doc.paid_amount)}${amount("БАҚИЯ:", doc.change_amount)}${Number(doc.outstanding_amount) ? amount(doc.is_return ? "БА ТАВОЗУНИ МУШТАРӢ:" : "ҚАРЗ:", doc.outstanding_amount) : ""}</section>
	<section class="section final-total">${amount("ҲАМАГӢ:", totals.total, "grand")}${taxRows.map((tax: any) => `<div class="tax-description">${escape(tax.description)}</div>${amount(`${tax.included_in_print_rate ? "Аз ҷумла андоз" : "Андоз"} ${Number(tax.rate) || 0}%:`, tax.amount)}`).join("")}</section>
	${doc.customer_name && (doc.loyalty_points != null || doc.stored_value_balance != null) ? `<section class="section customer">${doc.loyalty_points != null ? pair("ХОЛҲО:", doc.loyalty_points) : ""}${doc.stored_value_balance != null ? amount("ТАВОЗУНИ МУШТАРӢ:", doc.stored_value_balance) : ""}</section>` : ""}
	<div class="barcode">${barcode}</div><div class="invoice-id">${escape(doc.name)}</div><footer class="section footer"><div class="thanks">Ташаккур барои харид!</div></footer></body></html>`;
}

export async function printMarketReceipt(doc: { name: string; doctype?: string }, profile: any) {
	// Reserve the popup synchronously, while the cashier's click is active.
	const desktop = (window as any).electronAPI?.printStoreReceipt;
	const useQz = shouldUseConfiguredQzDocumentPrinting(profile);
	const win = useQz || desktop ? null : window.open("", "_blank");
	try {
		const result = await frappe.call("posawesome.posawesome.api.market_checkout.receipt_data", {
			invoice_name: doc.name, doctype: doc.doctype || (profile.create_pos_invoice_instead_of_sales_invoice ? "POS Invoice" : "Sales Invoice"),
		});
		const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		JsBarcode(svg, result.message.name, { format: "CODE128", displayValue: false, height: 40, margin: 8, width: 1.5 });
		const html = renderMarketReceipt(result.message, svg.outerHTML);
		if (desktop) {
			await desktop({ html, printerName: profile?.posa_qz_printer_name || "", silent: useQz });
			return;
		}
		if (useQz) {
			try { await printHtmlViaQz(html, { widthMm: 80, printerName: profile.posa_qz_printer_name }); return; }
			catch (error) { if (!confirmDocumentPrintFallback(error)) return; }
		}
		const target = win || window.open("", "_blank");
		if (!target) throw new Error("Allow popups to print a store receipt");
		target.document.write(html);
		target.document.close();
		await target.document.fonts?.ready;
		target.focus();
		target.print();
	} catch (error) { win?.close(); throw error; }
}
