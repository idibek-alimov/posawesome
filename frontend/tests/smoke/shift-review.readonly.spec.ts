import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({
	launchOptions: {
		executablePath: process.env.POSA_SMOKE_BROWSER_EXECUTABLE || undefined,
	},
});

test.skip(
	process.env.POSA_SHIFT_REVIEW_SMOKE !== "1" ||
		!process.env.POSA_SMOKE_BASE_URL,
	"Enable POSA_SHIFT_REVIEW_SMOKE with an explicitly configured migrated site.",
);

test("shared expense entry opens with native required date and note controls", async ({
	page,
}) => {
	const errors: string[] = [];
	page.on("pageerror", (error) => errors.push(error.message));
	if (process.env.POSA_SMOKE_USER && process.env.POSA_SMOKE_PASSWORD) {
		const response = await page.request.post("/api/method/login", {
			form: {
				usr: process.env.POSA_SMOKE_USER,
				pwd: process.env.POSA_SMOKE_PASSWORD,
			},
		});
		expect(response.ok()).toBeTruthy();
	}
	for (const route of [
		"expense-desk",
		...(process.env.POSA_SHIFT_REVIEW_NAME
			? [
					`shift-review/${encodeURIComponent(process.env.POSA_SHIFT_REVIEW_NAME)}`,
				]
			: []),
	]) {
		await page.goto(`/app/${route}`, { waitUntil: "domcontentloaded" });
		if (route === "expense-desk") {
			await expect(page.locator(".ed-summary strong")).toHaveCount(3);
			await page
				.locator(".page-container:visible .primary-action:visible")
				.click();
		} else {
			await expect(
				page.locator(".shift-review-page:visible"),
			).toHaveAttribute("aria-busy", "false");
			// A supplied review must have an actionable shortage for this entry check.
			await page
				.locator('[data-action="Missing expense"]')
				.first()
				.click();
		}
		const dialog = page.locator(".expense-desk-dialog:visible");
		await expect(dialog).toBeVisible();
		await expect(
			dialog.locator('[data-fieldname="posting_date"] input'),
		).not.toHaveValue("");
		await expect(
			dialog.locator('[data-fieldname="category"] select option'),
		).not.toHaveCount(1);
		// Category defaults must be applied, and newly required notes must expand safely.
		await dialog
			.locator('[data-fieldname="category"] select')
			.selectOption({ index: 1 });
		await expect
			.poll(() =>
				page.evaluate(() =>
					Boolean(
						(window as unknown as { cur_dialog: unknown })
							.cur_dialog,
					),
				),
			)
			.toBeTruthy();
		await page.evaluate(async () => {
			const { cur_dialog: current } = window as unknown as {
				cur_dialog: {
					set_df_property: (
						field: string,
						property: string,
						value: boolean,
					) => void;
					refresh_section_collapse: () => void;
				};
			};
			current.set_df_property("description", "reqd", true);
			current.refresh_section_collapse();
		});
		await expect(
			dialog.locator('[data-fieldname="description"] textarea'),
		).toBeVisible();
		await dialog
			.locator('[data-fieldname="description"] textarea')
			.fill("Read-only form regression");
		if (route.startsWith("shift-review/")) {
			await dialog
				.locator('[data-fieldname="correction_reason"] textarea')
				.fill("Read-only confirmation check");
			await dialog.locator(".modal-footer .btn-primary").click();
			const confirmation = page.locator(
				".modal:visible:not(.expense-desk-dialog)",
			);
			await expect(
				confirmation.locator(".frappe-confirm-message"),
			).toBeVisible();
			// Cancel at the final confirmation; no expense or review action is sent.
			await confirmation
				.locator(".modal-header .btn-modal-close")
				.click();
			await expect(confirmation).toBeHidden();
			await expect(
				dialog.locator(".modal-footer .btn-primary"),
			).toBeEnabled();
		}
		await dialog.locator(".modal-header .btn-modal-close").click();
		await expect(dialog).toBeHidden();
	}
	expect(errors).toEqual([]);
});

for (const sample of [
	{ lang: "en", width: 1440, theme: "light" },
	{ lang: "ru", width: 1440, theme: "light" },
	{ lang: "tg", width: 390, theme: "dark" },
]) {
	for (const route of ["expense-desk", "shift-review"]) {
		test(`${route} native ${sample.lang} ${sample.width} ${sample.theme}`, async ({
			page,
		}) => {
			const errors: string[] = [];
			page.on("pageerror", (error) => errors.push(error.message));
			await page.setViewportSize({ width: sample.width, height: 900 });
			const username =
				process.env[`POSA_SMOKE_USER_${sample.lang.toUpperCase()}`] ||
				process.env.POSA_SMOKE_USER;
			const password =
				process.env[
					`POSA_SMOKE_PASSWORD_${sample.lang.toUpperCase()}`
				] || process.env.POSA_SMOKE_PASSWORD;
			if (username && password) {
				const response = await page.request.post("/api/method/login", {
					form: { usr: username, pwd: password },
				});
				expect(response.ok()).toBeTruthy();
			}
			await page.goto(`/app/${route}?_lang=${sample.lang}`, {
				waitUntil: "domcontentloaded",
			});
			const screen = page.locator(`.${route}-page:visible`);
			await expect(screen).toBeVisible();
			expect(
				await page.evaluate(
					() =>
						(
							window as unknown as {
								frappe: { boot: { lang: string } };
							}
						).frappe.boot.lang,
				),
			).toBe(sample.lang);
			await page.evaluate(
				(theme) =>
					document.documentElement.setAttribute("data-theme", theme),
				sample.theme,
			);
			if (route === "shift-review") {
				await expect(screen).toHaveAttribute("aria-busy", "false");
				await expect(screen.locator(".sr-filters")).toBeVisible();
			} else {
				await expect(screen.locator(".ed-summary strong")).toHaveCount(
					3,
				);
				if (process.env.POSA_SHIFT_REVIEW_COMPANY) {
					await screen.locator(".ed-more > summary").click();
					const company = screen.locator(".ed-company input").first();
					await company.fill(process.env.POSA_SHIFT_REVIEW_COMPANY);
					await company.press("Tab");
					await expect(screen.locator(".ed-scope")).toContainText(
						process.env.POSA_SHIFT_REVIEW_COMPANY,
					);
					await screen.locator(".ed-more > summary").click();
				}
			}
			expect(
				await page.evaluate(
					() => document.documentElement.scrollWidth <= innerWidth,
				),
			).toBeTruthy();
			await page.keyboard.press("Tab");
			expect(
				await page.evaluate(
					() => document.activeElement !== document.body,
				),
			).toBeTruthy();
			expect(errors).toEqual([]);
			const accessibility = await new AxeBuilder({ page })
				.include(`.${route}-page`)
				.withTags(["wcag2a", "wcag2aa"])
				.analyze();
			expect(
				accessibility.violations.map((violation) => violation.id),
			).toEqual([]);
			await page.screenshot({
				path: test.info().outputPath(`${route}-${sample.lang}.png`),
				fullPage: true,
			});
			if (
				route === "expense-desk" &&
				(await screen.locator("[data-expense]").count())
			) {
				await screen.locator("[data-expense]").first().click();
				await expect(page.locator(".ed-detail:visible")).toBeVisible();
				await expect(
					page.locator(
						".ed-detail:visible a[href*='/app/quick-expense/']",
					),
				).toBeVisible();
				await page.screenshot({
					path: test
						.info()
						.outputPath(`expense-detail-${sample.lang}.png`),
					fullPage: true,
				});
			}
			const review = process.env.POSA_SHIFT_REVIEW_NAME;
			if (route === "shift-review" && review) {
				await page.goto(
					`/app/shift-review/${encodeURIComponent(review)}`,
					{ waitUntil: "domcontentloaded" },
				);
				await expect(screen).toHaveAttribute("aria-busy", "false");
				await expect(
					screen
						.locator("a[href*='/app/pos-closing-shift/']")
						.first(),
				).toBeVisible();
				await expect(
					screen.locator("a[href*='/app/journal-entry/']").first(),
				).toBeVisible();
				await page.screenshot({
					path: test
						.info()
						.outputPath(`review-detail-${sample.lang}.png`),
					fullPage: true,
				});
			}
			expect(
				await page.evaluate(
					() => document.documentElement.scrollWidth <= innerWidth,
				),
			).toBeTruthy();
			expect(errors).toEqual([]);
		});
	}
}
