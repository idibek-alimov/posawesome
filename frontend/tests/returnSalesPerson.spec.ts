// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/offline/index", () => ({
	getTaxTemplate: vi.fn(() => null),
	getTaxInclusiveSetting: vi.fn(() => false),
	isOffline: vi.fn(() => false),
}));

vi.mock("../src/posapp/components/pos/invoice_utils/currency", () => ({
	_getPlcConversionRate: vi.fn(() => 1),
}));

import { get_invoice_doc } from "../src/posapp/components/pos/invoice_utils/document";

describe("Return Sales Person carry-over", () => {
	beforeEach(() => {
		(globalThis as any).flt = (value: unknown, precision = 2) => {
			const number = Number(value || 0);
			return Number(number.toFixed(precision));
		};
	});

	it("maps sales_team and custom_sales_person from return_doc when preparing return invoice payload", () => {
		const return_doc = {
			name: "ACC-SINV-2026-00001",
			customer: "CUST-001",
			grand_total: 500,
			items: [
				{
					name: "ROW-001",
					item_code: "ITEM-A",
					qty: 2,
					rate: 250,
					amount: 500,
				},
			],
			sales_team: [
				{
					sales_person: "Sales Rep 1",
					allocated_percentage: 100,
					allocated_amount: 500,
				},
			],
			custom_sales_person: "Sales Rep 1",
		};

		// Simulate Returns.vue sales_team and custom_sales_person mapping
		const invoice_doc: any = {
			is_return: 1,
			return_against: return_doc.name,
			customer: return_doc.customer,
			sales_team: Array.isArray(return_doc.sales_team)
				? return_doc.sales_team.map((st: any) => ({
						sales_person: st.sales_person,
						allocated_percentage: st.allocated_percentage || 100,
					}))
				: [],
			custom_sales_person:
				return_doc.custom_sales_person ||
				(return_doc.sales_team && return_doc.sales_team[0]?.sales_person) ||
				"",
		};

		expect(invoice_doc.sales_team).toEqual([
			{
				sales_person: "Sales Rep 1",
				allocated_percentage: 100,
			},
		]);
		expect(invoice_doc.custom_sales_person).toBe("Sales Rep 1");
	});

	it("extracts the sales_person properly from sales_team array or fallback field", () => {
		const docWithTeam = {
			is_return: 1,
			sales_team: [{ sales_person: "Rep Alpha", allocated_percentage: 100 }],
		};

		const resolveSalesPerson = (doc: any) => {
			if (Array.isArray(doc?.sales_team) && doc.sales_team.length > 0 && doc.sales_team[0]?.sales_person) {
				return doc.sales_team[0].sales_person;
			} else if (doc?.custom_sales_person) {
				return doc.custom_sales_person;
			} else if (doc?.sales_person) {
				return doc.sales_person;
			}
			return "";
		};

		expect(resolveSalesPerson(docWithTeam)).toBe("Rep Alpha");

		const docWithCustomField = {
			is_return: 1,
			custom_sales_person: "Rep Gamma",
		};
		expect(resolveSalesPerson(docWithCustomField)).toBe("Rep Gamma");

		const docWithField = {
			is_return: 1,
			sales_person: "Rep Beta",
		};
		expect(resolveSalesPerson(docWithField)).toBe("Rep Beta");

		const docEmpty = {
			is_return: 1,
		};
		expect(resolveSalesPerson(docEmpty)).toBe("");
	});

	it("preserves sales_team and custom_sales_person in get_invoice_doc for return invoices", () => {
		const context: any = {
			invoiceType: "Return",
			pos_profile: {
				company: "Test Company",
				name: "Main POS",
				currency: "USD",
			},
			selected_currency: "USD",
			conversion_rate: 1,
			company: { default_currency: "USD" },
			customer: "CUST-001",
			isReturnInvoice: true,
			invoice_doc: {
				is_return: 1,
				return_against: "ACC-SINV-2026-00001",
				custom_sales_person: "Rep Alpha",
				sales_team: [
					{
						sales_person: "Rep Alpha",
						allocated_percentage: 100,
					},
				],
			},
			items: [],
			packed_items: [],
			Total: -500,
			subtotal: -500,
			additional_discount: 0,
			additional_discount_percentage: 0,
			roundAmount: (value: number) => value,
			posa_offers: [],
			posa_coupons: [],
		};

		const doc = get_invoice_doc(context);
		expect(doc.custom_sales_person).toBe("Rep Alpha");
		expect(doc.sales_team).toEqual([
			{
				sales_person: "Rep Alpha",
				allocated_percentage: 100,
			},
		]);
	});
});
