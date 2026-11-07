// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, h } from "vue";
import ShiftReviewNotice from "../src/posapp/components/pos/shift/ShiftReviewNotice.vue";
import { useUIStore } from "../src/posapp/stores/uiStore";

const review = (name = "OLD", remaining = -50) => ({
	review: name,
	closing_shift: `CLOSE-${name}`,
	status: remaining ? "Pending review" : "Resolved",
	currency: "TJS",
	currency_precision: 2,
	cashier_reason: "Taxi",
	accounts: [
		{
			methods: ["Cash"],
			expected_amount: 1000,
			actual_amount: 950,
			original_difference: -50,
			remaining_amount: remaining,
		},
	],
});
let wrapper: any, call: any;
const mountNotice = () =>
	mount(ShiftReviewNotice, {
		props: { posProfile: "Register" },
		global: {
			components: {
				VBtn: defineComponent({
					setup(_, { slots, attrs }) {
						return () => h("button", attrs, slots.default?.());
					},
				}),
			},
		},
	});
beforeEach(() => {
	setActivePinia(createPinia());
	vi.stubGlobal("frappe", {
		session: { user: "cashier" },
		boot: { lang: "ru" },
		confirm: (_text: string, yes: () => void) => yes(),
	});
	vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
	call = vi.fn(async ({ method }: any) => ({
		message: method.endsWith("get_register_context")
			? {
					available: true,
					total: 1,
					reviews: [review()],
					latest: review(),
				}
			: {
					...review(),
					available: true,
					transfer_state: "Not recorded",
					counted_cash: 950,
					can_transfer: false,
				},
	}));
	(globalThis as any).frappe.call = call;
});
afterEach(() => {
	wrapper?.unmount();
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
});
describe("previous shifts at opening", () => {
	it("shows origin and outstanding amount separately without emitting an opening amount or management controls", async () => {
		wrapper = mountNotice();
		await flushPromises();
		expect(wrapper.text()).toContain("CLOSE-OLD");
		expect(wrapper.text()).toContain("-50");
		expect(wrapper.text()).toContain("not added to the opening float");
		expect(wrapper.find("input").exists()).toBe(false);
		expect(wrapper.find("a").exists()).toBe(false);
		expect(wrapper.emitted()).toEqual({});
		expect(
			call.mock.calls.every(([args]: any[]) => typeof args === "object"),
		).toBe(true);
	});
	it("refreshes partial/resolved status from the server while retaining the original count", async () => {
		wrapper = mountNotice();
		await flushPromises();
		call.mockImplementation(async ({ method }: any) => ({
			message: method.endsWith("get_register_context")
				? {
						available: true,
						total: 0,
						reviews: [],
						latest: review("OLD", 0),
					}
				: { ...review("OLD", 0), available: true },
		}));
		await wrapper.get("button").trigger("click");
		await flushPromises();
		expect(wrapper.text()).toContain("Resolved");
		expect(wrapper.text()).toContain("Original difference: -50");
		expect(wrapper.text()).toContain("Remaining: 0");
	});
	it("ignores a late response after the selected register changes", async () => {
		let release: any;
		call.mockImplementationOnce(
			() =>
				new Promise((resolve) => {
					release = resolve;
				}),
		);
		wrapper = mountNotice();
		await flushPromises();
		await wrapper.setProps({ posProfile: "Other" });
		await flushPromises();
		release({
			message: {
				available: true,
				total: 1,
				reviews: [review("STALE")],
				latest: review("STALE"),
			},
		});
		await flushPromises();
		expect(wrapper.text()).not.toContain("STALE");
	});
	it("failed history and offline states cannot masquerade as zero outstanding", async () => {
		call.mockRejectedValue(new Error("Not permitted"));
		wrapper = mountNotice();
		await flushPromises();
		expect(wrapper.get('[role="alert"]').text()).toContain("Not permitted");
		expect(wrapper.text()).not.toContain("No unresolved");
		vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
		window.dispatchEvent(new Event("offline"));
		await flushPromises();
		expect(wrapper.text()).toContain("Reconnect");
	});
	it("lost transfer response recovers the original outcome without closing or printing again", async () => {
		let transferred = false;
		call.mockImplementation(async (args: any) => {
			if (typeof args === "string") {
				transferred = true;
				throw new Error("Response lost");
			}
			if (args.method.endsWith("get_register_context"))
				return {
					message: {
						available: true,
						total: 1,
						reviews: [review()],
						latest: review(),
					},
				};
			return {
				message: {
					...review(),
					available: true,
					can_transfer: true,
					counted_cash: 950,
					transfer_state: transferred ? "Complete" : "Not recorded",
				},
			};
		});
		wrapper = mountNotice();
		await flushPromises();
		await wrapper
			.findAll("button")
			.find((b: any) => b.text().includes("Check / retry"))
			.trigger("click");
		await flushPromises();
		expect(wrapper.text()).toContain("Safe transfer: Complete");
		expect(wrapper.text()).not.toContain("Response lost");
		expect(
			call.mock.calls.filter(([args]: any[]) => typeof args === "string"),
		).toHaveLength(1);
		expect(
			call.mock.calls.some(([args]: any[]) =>
				String(args?.method || args).includes("submit_closing"),
			),
		).toBe(false);
	});
	it("unconfirmed fiscal printing has a recovery notice and no automatic second print", async () => {
		useUIStore().lastClosedShift = {
			user: "cashier",
			name: "CLOSE-OLD",
			print_state: "Unknown",
		};
		wrapper = mountNotice();
		await flushPromises();
		expect(wrapper.text()).toContain("Check the printer journal");
		expect(wrapper.text()).toContain("already closed");
	});
});
