// @vitest-environment jsdom
import { h, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { afterEach, describe, expect, it, vi } from "vitest";
import CashMovementView from "../src/posapp/components/pos/cash/CashMovementView.vue";
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../src/offline", () => ({
	getPendingOfflineCashMovementCount: () => 1,
	getOfflineCashMovements: () => [],
	isOffline: () => false,
	saveOfflineCashMovement: vi.fn(),
	syncOfflineCashMovements: vi.fn(),
}));
vi.mock("../src/posapp/composables/pos/cash/useCashMovement", () => ({
	useCashMovement: () => ({
		loading: ref(false),
		submitting: ref(false),
		actionLoading: ref(false),
		context: ref({ enable_cash_movement: false }),
		historyRows: ref([]),
		error: ref(""),
		loadContext: vi.fn(),
		loadHistory: vi.fn(),
		cancelMovement: vi.fn(),
		deleteMovement: vi.fn(),
	}),
}));
let wrapper: any;
afterEach(() => wrapper?.unmount());
async function open(call: any) {
	(globalThis as any).frappe = { call };
	wrapper = mount(CashMovementView, {
		global: {
			plugins: [createPinia()],
			stubs: {
				CashMovementForm: true,
				CashMovementHistory: true,
				VRow: { render: () => h("div") },
				VBtn: true,
				VAlert: true,
			},
		},
	});
	await flushPromises();
	return wrapper.vm.$.setupState as any;
}
describe("legacy movement status recovery", () => {
	it("reads an original dead-letter result without resubmitting or changing queue evidence", async () => {
		const call = vi.fn(async () => ({
			message: {
				name: "CM-OLD",
				status: "submitted",
				docstatus: 1,
				journal_entry: "JE-OLD",
			},
		}));
		const vm = await open(call),
			request = {
				queue_id: 1,
				client_request_id: "original-id",
				hasRequestId: true,
				status: "dead_letter",
				payload: { amount: 50 },
			};
		const before = JSON.stringify(request);
		await vm.checkRequest(request);
		expect(call).toHaveBeenCalledWith({
			method: "posawesome.posawesome.api.cash_movement.service.get_cash_movement_request_outcome",
			args: { client_request_id: "original-id" },
		});
		expect(JSON.stringify(request)).toBe(before);
		expect(vm.requestResults[1].name).toBe("CM-OLD");
	});
	it("retains cancelled and missing results for manager review", async () => {
		for (const status of ["cancelled", "not_found"]) {
			const vm = await open(
				vi.fn(async () => ({
					message: {
						status,
						name: status === "cancelled" ? "CM-OLD" : undefined,
					},
				})),
			);
			await vm.checkRequest({
				queue_id: 1,
				client_request_id: "original-id",
				hasRequestId: true,
			});
			expect(vm.requestResults[1].message).toMatch(
				/retained|Keep the request/,
			);
			wrapper.unmount();
		}
	});
	it("never invents an ID to check malformed legacy requests", async () => {
		const call = vi.fn(),
			vm = await open(call);
		await vm.checkRequest({ queue_id: 1, hasRequestId: false });
		expect(call).not.toHaveBeenCalled();
	});
});
