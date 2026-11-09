// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/posapp/composables/core/useTheme", () => ({
	useTheme: () => ({}),
}));

vi.mock("../src/offline/index", () => ({
	getTaxTemplate: vi.fn(() => null),
	getTaxInclusiveSetting: vi.fn(() => false),
	isOffline: vi.fn(() => false),
}));

vi.mock("../src/posapp/components/pos/invoice_utils/currency", () => ({
	_getPlcConversionRate: vi.fn(() => 1),
}));

vi.mock("../src/posapp/plugins/print", () => ({
	appendDebugPrintParam: (url: string) => url,
	isDebugPrintEnabled: () => false,
	silentPrint: vi.fn(),
	watchPrintWindow: vi.fn(),
}));
vi.mock("../src/posapp/services/qzTray", () => ({
	printDocumentViaQz: vi.fn(),
}));

import {
	copySalesTeam,
	resolveSalesPerson,
} from "../src/posapp/utils/salesTeam";
import InvoiceManagement from "../src/posapp/components/pos/flows/InvoiceManagement.vue";
import Returns from "../src/posapp/components/pos/flows/Returns.vue";
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
			sales_team: copySalesTeam(return_doc.sales_team),
			custom_sales_person:
				return_doc.custom_sales_person ||
				(return_doc.sales_team &&
					return_doc.sales_team[0]?.sales_person) ||
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
			sales_team: [
				{ sales_person: "Rep Alpha", allocated_percentage: 100 },
			],
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

describe("actual return reconstruction", () => {
	for (const management of [false, true]) {
		for (const doctype of ["Sales Invoice", "POS Invoice"]) {
			it(`preserves zero and decimal split and item/payment lineage for ${doctype} via ${management ? "management" : "returns"}`, async () => {
				const original: any = {
					doctype,
					name: "ORIGINAL",
					customer: "Customer",
					grand_total: 200,
					paid_amount: 200,
					discount_amount: 10,
					additional_discount_percentage: 5,
					sales_team: [
						{
							sales_person: "A",
							allocated_percentage: 0,
							allocated_amount: 0,
						},
						{
							sales_person: "B",
							allocated_percentage: 33.3333,
							allocated_amount: 66.6666,
						},
						{
							sales_person: "C",
							allocated_percentage: 66.6667,
							allocated_amount: 133.3334,
						},
					],
					items: [
						{
							name: "original-row",
							item_code: "Item",
							qty: 2,
							stock_qty: 4,
							conversion_factor: 2,
							uom: "Box",
							rate: 100,
							price_list_rate: 110,
							discount_percentage: 5,
							discount_amount: 10,
							amount: 200,
							net_amount: 200,
						},
					],
					payments: [
						{
							mode_of_payment: "Cash",
							amount: 200,
							base_amount: 400,
							currency: "USD",
							conversion_rate: 2,
						},
					],
				};
				(globalThis as any).frappe = {
					call: vi.fn(async () => ({ message: original })),
				};
				const emit = vi.fn();
				if (management) {
					await (InvoiceManagement as any).methods.createReturn.call(
						{
							posProfile: { name: "Profile", company: "Company" },
							eventBus: { emit },
							uiStore: { closeInvoiceManagement: vi.fn() },
							toastStore: { show: vi.fn() },
						},
						original,
					);
				} else {
					await (Returns as any).methods.submit_dialog.call({
						selected: [{ name: original.name }],
						pos_profile: {
							name: "Profile",
							create_pos_invoice_instead_of_sales_invoice: Number(
								doctype === "POS Invoice",
							),
						},
						company: "Company",
						flt: Number,
						currency_precision: 2,
						eventBus: { emit },
					});
				}
				const [event, { invoice_doc: doc, return_doc }] =
					emit.mock.calls[0];
				expect(event).toBe("load_return_invoice");
				expect(return_doc).toBe(original);
				expect(doc.sales_team).toEqual(
					copySalesTeam(original.sales_team),
				);
				expect(doc.custom_sales_person).toBe("A");
				expect(
					doc.sales_team.every(
						(r: any) => r.allocated_amount === undefined,
					),
				).toBe(true);
				expect(
					doc.items[0][
						doctype === "POS Invoice"
							? "pos_invoice_item"
							: "sales_invoice_item"
					],
				).toBe("original-row");
				expect(doc.items[0]).toMatchObject({
					qty: -2,
					stock_qty: -4,
					conversion_factor: 2,
					uom: "Box",
					rate: 100,
					discount_percentage: 5,
				});
				expect(doc.payments[0]).toMatchObject({
					amount: management ? 200 : -200,
					base_amount: management ? 400 : -400,
					currency: "USD",
					conversion_rate: 2,
				});
				expect(doc.grand_total).toBe(-200);
				expect(doc.discount_amount).toBe(10);
				expect(doc.company).toBe("Company");
				expect(doc.pos_profile).toBe("Profile");
			});
		}
	}
});
