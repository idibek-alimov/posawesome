import { describe, expect, it } from "vitest";

import { useItemsSearch } from "../src/posapp/composables/pos/items/store/useItemsSearch";

describe("useItemsSearch fuzzy local matching", () => {
	it("matches a near item-name typo without requiring a server miss fallback", () => {
		const search = useItemsSearch();
		const items = [
			{
				item_code: "CHOCO-BISCUIT",
				item_name: "Chocolate Biscuit",
				item_group: "Snacks",
			},
			{
				item_code: "VANILLA-CAKE",
				item_name: "Vanilla Cake",
				item_group: "Bakery",
			},
		] as any[];

		search.updateIndexes(items, null);

		const result = search.performLocalSearch(
			"choclate",
			items,
			"ALL",
		);

		expect(result.map((item) => item.item_code)).toEqual([
			"CHOCO-BISCUIT",
		]);
	});

	it("keeps item group filtering active for fuzzy matches", () => {
		const search = useItemsSearch();
		const items = [
			{
				item_code: "CHOCO-BISCUIT",
				item_name: "Chocolate Biscuit",
				item_group: "Snacks",
			},
			{
				item_code: "CHOCO-CAKE",
				item_name: "Chocolate Cake",
				item_group: "Bakery",
			},
		] as any[];

		search.updateIndexes(items, null);

		const result = search.performLocalSearch(
			"choclate",
			items,
			"Bakery",
		);

		expect(result.map((item) => item.item_code)).toEqual(["CHOCO-CAKE"]);
	});

	it("indexes item codes and barcodes in normalized lookup maps", () => {
		const search = useItemsSearch();
		const items = [
			{
				item_code: "MED-001",
				item_name: "Medicine",
				item_group: "Pharmacy",
				item_barcode: [{ barcode: "ABC123" }],
				barcodes: ["98765"],
			},
		] as any[];

		search.updateIndexes(items, null);

		expect(search.getItemByCode("med-001")?.item_code).toBe("MED-001");
		expect(search.getItemByBarcode("abc123")?.item_code).toBe("MED-001");
		expect(search.getItemByBarcode("98765")?.item_code).toBe("MED-001");
	});

	it("ranks exact code and barcode matches before broader name matches", () => {
		const search = useItemsSearch();
		const items = [
			{
				item_code: "PARA-500",
				item_name: "Paracetamol 500",
				item_group: "Pharmacy",
			},
			{
				item_code: "OTHER",
				item_name: "Para Support",
				item_group: "Pharmacy",
				item_barcode: [{ barcode: "PARA" }],
			},
		] as any[];

		search.updateIndexes(items, null);

		const result = search.performRankedLocalSearch(
			"PARA",
			items,
			"ALL",
			10,
		);

		expect(result.map((item) => item.item_code)).toEqual([
			"OTHER",
			"PARA-500",
		]);
	});

	it("matches items by Cyrillic name and short query substrings", () => {
		const search = useItemsSearch();
		const items = [
			{
				item_code: "112-BLA",
				item_name: "p1 (Черный)",
				item_group: "Apparel",
			},
			{
				item_code: "112-WHI",
				item_name: "p1 (Белый)",
				item_group: "Apparel",
			},
			{
				item_code: "TEA-TJ",
				item_name: "Чои кабуд",
				item_group: "Beverages",
			},
		] as any[];

		search.updateIndexes(items, null);

		// Cyrillic search with 'й'
		const blackResult = search.performRankedLocalSearch("Черный", items, "ALL", 10);
		expect(blackResult.map((i) => i.item_code)).toEqual(["112-BLA"]);

		// Substring search with 'Белый'
		const whiteResult = search.performRankedLocalSearch("Белый", items, "ALL", 10);
		expect(whiteResult.map((i) => i.item_code)).toEqual(["112-WHI"]);

		// Short 2-character query 'p1'
		const p1Result = search.performRankedLocalSearch("p1", items, "ALL", 10);
		expect(p1Result.map((i) => i.item_code)).toEqual(["112-BLA", "112-WHI"]);

		// Search with Tajik character
		const teaResult = search.performRankedLocalSearch("чой", items, "ALL", 10);
		expect(teaResult.map((i) => i.item_code)).toEqual(["TEA-TJ"]);
	});

	it("returns all items when search query is empty or cleared", () => {
		const search = useItemsSearch();
		const items = [
			{ item_code: "112-BLA", item_name: "p1 (Черный)", item_group: "Apparel" },
			{ item_code: "112-WHI", item_name: "p1 (Белый)", item_group: "Apparel" },
			{ item_code: "TEA-TJ", item_name: "Чои кабуд", item_group: "Beverages" },
		] as any[];

		search.updateIndexes(items, null);

		// Non-empty search filters items
		expect(search.performRankedLocalSearch("Черный", items, "ALL", 10).map((i) => i.item_code)).toEqual(["112-BLA"]);

		// Empty/cleared search returns all items
		expect(search.performRankedLocalSearch("", items, "ALL", 10).map((i) => i.item_code)).toEqual(["112-BLA", "112-WHI", "TEA-TJ"]);

		// Empty search with group filter returns all items in that group
		expect(search.performRankedLocalSearch("", items, "Apparel", 10).map((i) => i.item_code)).toEqual(["112-BLA", "112-WHI"]);
	});
});
