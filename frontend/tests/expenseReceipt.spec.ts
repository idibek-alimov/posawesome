// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	receiptUrl,
	uploadExpenseReceipt,
} from "../src/posapp/composables/pos/expenses/receipt";

describe("private native expense receipt", () => {
	beforeEach(() => {
		(window as any).frappe = { csrf_token: "csrf" };
	});
	afterEach(() => vi.unstubAllGlobals());
	it("uploads private with native CSRF without creating an expense", async () => {
		const fetch = vi.fn(async () => ({
			ok: true,
			json: async () => ({
				message: { file_url: "/private/files/tea.jpg" },
			}),
		}));
		vi.stubGlobal("fetch", fetch);
		expect(
			await uploadExpenseReceipt(
				new File(["photo"], "tea.jpg", { type: "image/jpeg" }),
			),
		).toBe("/private/files/tea.jpg");
		const [url, options] = fetch.mock.calls[0] as any;
		expect(url).toBe("/api/method/upload_file");
		expect(options.body.get("is_private")).toBe("1");
		expect(options.headers["X-Frappe-CSRF-Token"]).toBe("csrf");
		expect(options.credentials).toBe("same-origin");
	});
	it("rejects a public attachment and native denied upload", async () => {
		for (const [ok, file_url] of [
			[true, "/files/public.jpg"],
			[false, "/private/files/denied.jpg"],
		]) {
			vi.stubGlobal(
				"fetch",
				vi.fn(async () => ({
					ok,
					json: async () => ({ message: { file_url } }),
				})),
			);
			await expect(
				uploadExpenseReceipt(new File(["x"], "tea.jpg")),
			).rejects.toThrow(/not been submitted/);
		}
	});
	it("receipt links accept native paths and reject active or external URLs", () => {
		expect(receiptUrl("/private/files/receipt.jpg")).toBe(
			"/private/files/receipt.jpg",
		);
		expect(receiptUrl("/files/historical.pdf")).toBe(
			"/files/historical.pdf",
		);
		for (const url of [
			"javascript:alert(1)",
			"//remote/files/a",
			"https://remote/a",
			"/private/files/\\evil",
			null,
		])
			expect(receiptUrl(url)).toBeUndefined();
	});
});
