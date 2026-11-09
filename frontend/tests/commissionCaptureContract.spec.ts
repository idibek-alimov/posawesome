// S2e2 source-attribution regressions; no live commission capture.
import { beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("../src/offline/index", () => ({
	getTaxTemplate: vi.fn(() => null),
	getTaxInclusiveSetting: vi.fn(() => false),
	isOffline: vi.fn(() => false),
}));
vi.mock("../src/posapp/components/pos/invoice_utils/currency", () => ({
	_getPlcConversionRate: vi.fn(() => 1),
}));
import { ref, nextTick } from "vue";
import { usePaymentSalesPerson } from "../src/posapp/composables/pos/payments/usePaymentSalesPerson";
import { copySalesTeam } from "../src/posapp/utils/salesTeam";
import { get_invoice_doc } from "../src/posapp/components/pos/invoice_utils/document";

describe("recorded sales team preservation", () => {
	beforeEach(() => {
		(globalThis as any).flt = (v: unknown) => Number(v || 0);
	});
	for (const shares of [
		[0, 100],
		["0", "100"],
		[33.3333, 66.6667],
		[undefined, 100],
		[null, 100],
		["", 100],
		["bad", 100],
	]) {
		for (const isReturn of [false, true]) {
			it(`preserves zero share in ${isReturn ? "return" : "sale"} payload ${JSON.stringify(shares)}`, () => {
				const source = [
					{
						sales_person: "Zero share",
						allocated_percentage: shares[0],
					},
					{
						sales_person: "Full share",
						allocated_percentage: shares[1],
					},
				];
				const context: any = {
					invoiceType: isReturn ? "Return" : "Invoice",
					isReturnInvoice: isReturn,
					pos_profile: {
						company: "Test Company",
						name: "Test POS",
						currency: "TJS",
					},
					selected_currency: "TJS",
					conversion_rate: 1,
					company: { default_currency: "TJS" },
					customer: "Test Customer",
					invoice_doc: {
						sales_team: source,
						is_return: Number(isReturn),
					},
					items: [],
					packed_items: [],
					Total: isReturn ? -100 : 100,
					subtotal: isReturn ? -100 : 100,
					additional_discount: 0,
					additional_discount_percentage: 0,
					roundAmount: (n: number) => n,
					posa_offers: [],
					posa_coupons: [],
				};
				const doc = get_invoice_doc(context);
				expect(source.map((row) => row.allocated_percentage)).toEqual(
					shares,
				);
				expect(
					doc.sales_team.map((row: any) => row.allocated_percentage),
				).toEqual(shares);
			});
		}
	}
});

describe("payment salesperson hydration versus selection", () => {
	it("preserves a split on load, reopen, replacement and reactive flush", async () => {
		const source = {
			sales_team: [
				{ sales_person: "A", allocated_percentage: 0 },
				{ sales_person: "B", allocated_percentage: 100 },
			],
			custom_sales_person: "B",
		};
		const doc = ref<any>(JSON.parse(JSON.stringify(source)));
		const selection = usePaymentSalesPerson(doc);
		for (let i = 0; i < 3; i++) {
			doc.value = JSON.parse(JSON.stringify(source));
			expect(selection.value).toBe("A");
			await nextTick();
			expect(doc.value).toEqual(source);
		}
		doc.value = {};
		expect(selection.value).toBe("");
	});
	it("applies an intentional same-first-person selection and clears every alias", () => {
		const doc = ref<any>({
			sales_team: [
				{ sales_person: "A", allocated_percentage: 40 },
				{ sales_person: "B", allocated_percentage: 60 },
			],
			custom_sales_person: "A",
			sales_person: "stale",
		});
		const selection = usePaymentSalesPerson(doc);
		selection.value = "A";
		expect(doc.value.sales_team).toEqual([
			{ sales_person: "A", allocated_percentage: 100 },
		]);
		selection.value = "C";
		expect(doc.value.custom_sales_person).toBe("C");
		expect(doc.value.sales_person).toBe("C");
		selection.value = null;
		expect(selection.value).toBe("");
		expect(doc.value.sales_team).toEqual([]);
		expect(doc.value.custom_sales_person).toBe("");
		expect(doc.value.sales_person).toBe("");
	});
	it("reads legacy aliases without creating a team or guessing an actor", () => {
		for (const source of [
			{ custom_sales_person: "Legacy" },
			{ sales_person: "Legacy" },
			{},
		]) {
			const doc = ref<any>({ ...source });
			const selection = usePaymentSalesPerson(doc);
			expect(selection.value).toBe(
				Object.keys(source).length ? "Legacy" : "",
			);
			expect(doc.value).toEqual(source);
		}
	});
	it("copies only source attribution, without original positive allocated amounts", () => {
		const source = [
			{
				sales_person: "A",
				allocated_percentage: 0,
				allocated_amount: 999,
			},
		];
		expect(copySalesTeam(source)).toEqual([
			{ sales_person: "A", allocated_percentage: 0 },
		]);
		expect(copySalesTeam(null)).toEqual([]);
		expect(
			copySalesTeam([{ sales_person: "A" }])[0].allocated_percentage,
		).toBeUndefined();
	});
});
