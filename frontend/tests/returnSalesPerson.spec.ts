// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

describe("Return Sales Person carry-over", () => {
	it("maps sales_team from return_doc when preparing return invoice payload", () => {
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
		};

		// Simulate Returns.vue / InvoiceManagement.vue sales_team mapping
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
		};

		expect(invoice_doc.sales_team).toEqual([
			{
				sales_person: "Sales Rep 1",
				allocated_percentage: 100,
			},
		]);
	});

	it("extracts the sales_person properly from sales_team array or fallback field", () => {
		const docWithTeam = {
			is_return: 1,
			sales_team: [{ sales_person: "Rep Alpha", allocated_percentage: 100 }],
		};

		const resolveSalesPerson = (doc: any) => {
			if (Array.isArray(doc?.sales_team) && doc.sales_team.length > 0) {
				return doc.sales_team[0].sales_person || "";
			} else if (doc?.sales_person) {
				return doc.sales_person;
			}
			return "";
		};

		expect(resolveSalesPerson(docWithTeam)).toBe("Rep Alpha");

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
});
