// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";

import PaymentSelectionFields from "../src/posapp/components/pos/payments/PaymentSelectionFields.vue";

const VRowStub = {
	template: "<div><slot /></div>",
};

const VColStub = {
	template: "<div><slot /></div>",
};

describe("PaymentSelectionFields", () => {
	beforeEach(() => {
		(globalThis as any).window.__ = (text: string) => text;
		(globalThis as any).window.frappe = {
			_: (text: string) => text,
		};
	});

	it("hides the print format field when selection is disabled", () => {
		const wrapper = mount(PaymentSelectionFields, {
			props: {
				showPrintFormat: false,
			},
			global: {
				stubs: {
					"v-row": VRowStub,
					"v-col": VColStub,
					"v-select": true,
				},
			},
		});

		expect(wrapper.find(".print-format-card").exists()).toBe(false);
	});

	it("shows the print format field when selection is enabled", () => {
		const wrapper = mount(PaymentSelectionFields, {
			props: {
				showPrintFormat: true,
			},
			global: {
				stubs: {
					"v-row": VRowStub,
					"v-col": VColStub,
					"v-select": true,
				},
			},
		});

		expect(wrapper.find(".print-format-card").exists()).toBe(true);
	});
});
