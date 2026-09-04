import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import {
	resolveTemplateVars,
	useBarcodePrintOutput,
} from "../src/posapp/composables/pos/items/useBarcodePrintOutput";
import { useUIStore } from "../src/posapp/stores/uiStore";

describe("Barcode Label Templates & Output", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		const uiStore = useUIStore();
		uiStore.posProfile = {
			name: "POS Profile 1",
			company: "Radolfa",
			currency: "TJS",
		} as any;
	});

	it("formats price without trailing decimals for integers in resolveTemplateVars", () => {
		const item = {
			item_code: "1957",
			item_name: "Кепки восьмиклинки",
			barcode: "2001957000004",
			price: 1000,
			short_code: "1957",
			company: "Radolfa",
			currency: "TJS",
		};

		const result = resolveTemplateVars("{price}", item);
		expect(result).toBe("1,000 TJS");
	});

	it("formats price with 2 decimals when non-integer", () => {
		const item = {
			item_code: "1957",
			price: 1000.5,
			currency: "TJS",
		};

		const result = resolveTemplateVars("{price}", item);
		expect(result).toBe("1,000.50 TJS");
	});

	it("resolves short_code and company at top header", () => {
		const item = {
			item_code: "ITEM-001",
			custom_short_code: "4021",
			company: "Radolfa Store",
		};

		const result = resolveTemplateVars("{company} · #{short_code}", item);
		expect(result).toBe("Radolfa Store · #4021");
	});

	it("formats currency correctly in useBarcodePrintOutput", () => {
		const { formatCurrency } = useBarcodePrintOutput();
		expect(formatCurrency(1000)).toBe("1,000 TJS");
		expect(formatCurrency(90)).toBe("90 TJS");
		expect(formatCurrency(1250.75)).toBe("1,250.75 TJS");
	});

	it("generates label HTML with header containing company and short code and no 'Nos'", () => {
		const { generatePrintContent } = useBarcodePrintOutput();
		const items = [
			{
				item_code: "1957",
				item_name: "Кепки восьмиклинки",
				barcode: "2001957000004",
				qty: 1,
				price: 1000,
				uom: "Nos",
				short_code: "1957",
				company: "Radolfa",
			},
		];

		const html = generatePrintContent(items);
		expect(html).toContain("Radolfa");
		expect(html).toContain("#1957");
		expect(html).toContain("1,000 TJS");
		expect(html).not.toContain("<div class=\"uom-label\">Nos</div>");
		expect(html).toContain("class=\"label-header\"");
	});

	it("formats price_formatted with 2 decimals and no currency", () => {
		const item = {
			item_code: "1923",
			item_name: "Gabbiacci",
			barcode: "2001923000007",
			price: 365,
			custom_short_code: "1923",
			company: "RADOLFA",
		};

		const result = resolveTemplateVars("{price_formatted}", item);
		expect(result).toBe("365.00");
	});

	it("formats price_spaced and old_price_spaced with space before cents", () => {
		const item = {
			item_code: "3322",
			item_name: "KITON (DG)",
			barcode: "2003322000001",
			price: 115,
			old_price: 185,
			custom_short_code: "3322",
			company: "RADOLFA",
			uom: "Nos",
		};

		expect(resolveTemplateVars("{price_spaced}", item)).toBe("115 00");
		expect(resolveTemplateVars("{old_price_spaced}", item)).toBe("185 00");
		expect(resolveTemplateVars("Код: {short_code}", item)).toBe("Код: 3322");
		expect(resolveTemplateVars("Цена за: {uom}", item)).toBe("Цена за: шт");
	});

	it("renders Radolfa Standard template correctly with custom_short_code and price_formatted", () => {
		const { generatePrintContent, setDesignerTemplate } = useBarcodePrintOutput();
		const standardLayout = JSON.stringify([
			{ id: "company_header", type: "text", x: 2, y: 1.5, width: 54, height: 5.2, fontSize: 12, fontBold: true, textAlign: "center", color: "#000000", content: "{company}" },
			{ id: "item_name", type: "text", x: 2, y: 8.0, width: 54, height: 6.2, fontSize: 10.5, fontBold: false, textAlign: "center", color: "#000000", content: "{item_name}" },
			{ id: "barcode_center", type: "barcode", x: 3, y: 14.8, width: 52, height: 14.5, symbology: "EAN13", humanReadable: true, content: "{barcode}" },
			{ id: "short_code_val", type: "text", x: 3, y: 30.5, width: 14, height: 7.5, fontSize: 12, fontBold: false, textAlign: "left", color: "#000000", content: "{short_code}" },
			{ id: "price_val", type: "text", x: 18, y: 29.5, width: 37, height: 8.5, fontSize: 22, fontBold: true, textAlign: "center", color: "#000000", content: "{price_formatted}" },
		]);

		setDesignerTemplate(standardLayout);
		const items = [{
			item_code: "1923",
			item_name: "Gabbiacci",
			barcode: "2001923000007",
			price: 365,
			custom_short_code: "1923",
			company: "RADOLFA",
		}];

		const html = generatePrintContent(items);
		expect(html).toContain("RADOLFA");
		expect(html).toContain("Gabbiacci");
		expect(html).toContain("1923");
		expect(html).toContain("365.00");
		expect(html).toContain("2001923000007");
	});

	it("renders Radolfa Discount / Sale template correctly with АКЦИЯ!, strikethrough old price, code and sale price", () => {
		const { generatePrintContent, setDesignerTemplate } = useBarcodePrintOutput();
		const discountLayout = JSON.stringify([
			{ id: "company_header", type: "text", x: 2, y: 1.5, width: 54, height: 5.0, fontSize: 12, fontBold: true, textAlign: "center", color: "#000000", content: "{company}" },
			{ id: "item_name", type: "text", x: 2.5, y: 8.5, width: 32, height: 7.5, fontSize: 10.5, fontBold: true, textAlign: "left", color: "#000000", content: "{item_name}" },
			{ id: "promo_badge_text", type: "text", x: 2.5, y: 17.0, width: 23, height: 7.0, fontSize: 11, fontBold: true, textAlign: "center", color: "#ffffff", content: "АКЦИЯ!" },
			{ id: "old_price_val", type: "text", x: 28, y: 15.0, width: 28, height: 6.0, fontSize: 13.5, fontBold: true, textAlign: "right", color: "#000000", content: "{old_price_spaced}" },
			{ id: "short_code_text", type: "text", x: 2.5, y: 25.5, width: 24, height: 4.5, fontSize: 9.5, fontBold: true, textAlign: "left", color: "#000000", content: "Код: {short_code}" },
			{ id: "new_sale_price", type: "text", x: 27, y: 21.5, width: 29, height: 9.5, fontSize: 22, fontBold: true, textAlign: "right", color: "#000000", content: "{price_spaced}" },
			{ id: "uom_text", type: "text", x: 27, y: 32.5, width: 29, height: 4.8, fontSize: 9.5, fontBold: true, textAlign: "right", color: "#000000", content: "Цена за: {uom}" },
		]);

		setDesignerTemplate(discountLayout);
		const items = [{
			item_code: "3322",
			item_name: "KITON (DG)",
			barcode: "2003322000001",
			price: 115,
			old_price: 185,
			custom_short_code: "3322",
			company: "RADOLFA",
			uom: "шт",
		}];

		const html = generatePrintContent(items);
		expect(html).toContain("RADOLFA");
		expect(html).toContain("KITON (DG)");
		expect(html).toContain("АКЦИЯ!");
		expect(html).toContain("185 00");
		expect(html).toContain("Код: 3322");
		expect(html).toContain("115 00");
		expect(html).toContain("Цена за: шт");
	});

	it("hides old_price elements conditionally when old_price is not provided", () => {
		const { generatePrintContent, setDesignerTemplate } = useBarcodePrintOutput();
		const discountLayoutWithCondition = JSON.stringify([
			{ id: "item_name", type: "text", x: 2.5, y: 8.5, width: 32, height: 7.5, fontSize: 10, content: "{item_name}" },
			{ id: "old_price_val", type: "text", x: 28, y: 15.0, width: 28, height: 6.0, fontSize: 13, content: "{old_price_spaced}", condition: "{old_price} != ''" },
			{ id: "new_sale_price", type: "text", x: 27, y: 21.5, width: 29, height: 9.5, fontSize: 22, content: "{price_spaced}" },
		]);

		setDesignerTemplate(discountLayoutWithCondition);
		const itemsNoOldPrice = [{
			item_code: "PV-01-BLU",
			item_name: "Parent Variant-BLU",
			price: 100,
			company: "Radolfa",
		}];

		const html = generatePrintContent(itemsNoOldPrice);
		expect(html).toContain("Parent Variant-BLU");
		expect(html).toContain("100 00");
		expect(html).not.toContain("{old_price_spaced}");
	});

	it("falls back to standard_rate when standard_rate > rate and old_price is not set", () => {
		const item = {
			item_code: "PV-01-BLU",
			item_name: "Parent Variant-BLU",
			price: 100,
			standard_rate: 150,
		};

		expect(resolveTemplateVars("{old_price_spaced}", item)).toBe("150 00");
		expect(resolveTemplateVars("{price_spaced}", item)).toBe("100 00");
	});

	it("evaluates active pricing rules in barcode queue and sets old_price and discounted price", async () => {
		const { usePricingRulesStore } = await import("../src/posapp/stores/pricingRulesStore");
		const { useBarcodePrintQueue } = await import("../src/posapp/composables/pos/items/useBarcodePrintQueue");
		const pricingRulesStore = usePricingRulesStore();
		
		// Set pricing rule snapshot with 15% discount on PV-01-BLU
		pricingRulesStore.setSnapshot([
			{
				name: "PRLE-0001",
				item_code: "PV-01-BLU",
				price_or_product_discount: "Price",
				discount_type: "Rate",
				rate_or_discount_type: "Discount Percentage",
				rate_or_discount: 15.0,
				margin_type: "Percentage",
				margin_rate_or_amount: 0.0,
				priority: 2,
				specificity: 3,
			},
		], "test-ctx");

		const queue = useBarcodePrintQueue();
		const resolved = await queue.resolveItemPricingAndDiscount({
			item_code: "PV-01-BLU",
			item_name: "Parent Variant-BLU",
			price_list_rate: 100,
			rate: 100,
		});

		expect(resolved.old_price).toBe(100);
		expect(resolved.price).toBe(85);
		expect(resolved.discount).toBe("15%");
	});
});
