// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";

let currentRoutePath = "/pos";

vi.mock("../src/posapp/composables/core/useRtl", () => ({
	useRtl: () => ({
		isRtl: false,
		rtlClasses: [],
		rtlStyles: {},
	}),
}));

vi.mock("vue-router", () => ({
	useRoute: () => ({
		path: currentRoutePath,
	}),
}));

import NavbarDrawer from "../src/posapp/components/navbar/NavbarDrawer.vue";

const StubComponent = defineComponent({
	setup(_, { slots }) {
		return () =>
			h(
				"div",
				{},
				[slots.prepend?.(), slots.default?.(), slots.append?.()].filter(Boolean),
			);
	},
});

const defaultItems = [
	{ text: "POS", icon: "mdi-network-pos", to: "/pos", primary: true },
	{ text: "Expenses", icon: "mdi-cash-register", to: "/expenses", primary: true },
	{ text: "Awesome Dashboard", icon: "mdi-view-dashboard-outline", to: "/dashboard" },
	{ text: "Payments", icon: "mdi-credit-card", to: "/payments" },
	{ text: "Purchase Order", icon: "mdi-cart-plus", to: "/orders" },
	{ text: "Barcode Printing", icon: "mdi-barcode", to: "/barcode" },
];

describe("NavbarDrawer primary actions & collapsible secondary items", () => {
	beforeEach(() => {
		currentRoutePath = "/pos";
		vi.stubGlobal("__", (value: string) => value);
	});

	it("renders POS and Expenses as prominent primary items at the top", () => {
		const wrapper = mount(NavbarDrawer, {
			props: {
				drawer: true,
				company: "Radolfa",
				companyImg: "/logo.png",
				items: defaultItems,
			},
			global: {
				components: {
					VNavigationDrawer: StubComponent,
					VAvatar: StubComponent,
					VImg: StubComponent,
					VDivider: StubComponent,
					VList: StubComponent,
					VListItem: StubComponent,
					VListItemTitle: StubComponent,
					VIcon: StubComponent,
					VExpandTransition: StubComponent,
				},
			},
		});



		const primaryItems = wrapper.findAll(".drawer-item--primary");
		expect(primaryItems.length).toBe(2);
		expect(primaryItems[0].text()).toContain("POS");
		expect(primaryItems[1].text()).toContain("Expenses");

		// Primary title typography class
		const primaryTitles = wrapper.findAll(".drawer-item-title--primary");
		expect(primaryTitles.length).toBe(2);
	});

	it("keeps secondary items hidden by default and shows More options toggle with count", () => {
		const wrapper = mount(NavbarDrawer, {
			props: {
				drawer: true,
				company: "Radolfa",
				items: defaultItems,
			},
			global: {
				components: {
					VNavigationDrawer: StubComponent,
					VAvatar: StubComponent,
					VImg: StubComponent,
					VDivider: StubComponent,
					VList: StubComponent,
					VListItem: StubComponent,
					VListItemTitle: StubComponent,
					VIcon: StubComponent,
					VExpandTransition: StubComponent,
				},
			},
		});

		const moreToggle = wrapper.find('[data-test="drawer-more-toggle"]');
		expect(moreToggle.exists()).toBe(true);
		expect(moreToggle.attributes("aria-expanded")).toBe("false");
		expect(moreToggle.text()).toContain("More options");
		expect(moreToggle.text()).toContain("4"); // 4 secondary items

		const secondaryCollapse = wrapper.find('[data-test="drawer-secondary-collapse"]');
		expect(secondaryCollapse.attributes("style")).toContain("display: none");
	});

	it("expands secondary items when More options button is clicked and collapses when clicked again", async () => {
		const wrapper = mount(NavbarDrawer, {
			props: {
				drawer: true,
				company: "Radolfa",
				items: defaultItems,
			},
			global: {
				components: {
					VNavigationDrawer: StubComponent,
					VAvatar: StubComponent,
					VImg: StubComponent,
					VDivider: StubComponent,
					VList: StubComponent,
					VListItem: StubComponent,
					VListItemTitle: StubComponent,
					VIcon: StubComponent,
					VExpandTransition: StubComponent,
				},
			},
		});

		const moreToggle = wrapper.find('[data-test="drawer-more-toggle"]');
		await moreToggle.trigger("click");

		expect(moreToggle.attributes("aria-expanded")).toBe("true");
		expect(moreToggle.text()).toContain("Show less");

		const secondaryCollapse = wrapper.find('[data-test="drawer-secondary-collapse"]');
		expect(secondaryCollapse.attributes("style") || "").not.toContain("display: none");

		const secondaryItems = wrapper.findAll(".drawer-item--secondary");
		expect(secondaryItems.length).toBe(4);
		expect(secondaryItems[0].text()).toContain("Awesome Dashboard");
		expect(secondaryItems[1].text()).toContain("Payments");
		expect(secondaryItems[2].text()).toContain("Purchase Order");
		expect(secondaryItems[3].text()).toContain("Barcode Printing");

		// Click again to collapse
		await moreToggle.trigger("click");
		expect(moreToggle.attributes("aria-expanded")).toBe("false");
		expect(moreToggle.text()).toContain("More options");
		expect(secondaryCollapse.attributes("style")).toContain("display: none");
	});

	it("auto-expands secondary section if the active route is a secondary item", () => {
		currentRoutePath = "/barcode";

		const wrapper = mount(NavbarDrawer, {
			props: {
				drawer: true,
				company: "Radolfa",
				items: defaultItems,
			},
			global: {
				components: {
					VNavigationDrawer: StubComponent,
					VAvatar: StubComponent,
					VImg: StubComponent,
					VDivider: StubComponent,
					VList: StubComponent,
					VListItem: StubComponent,
					VListItemTitle: StubComponent,
					VIcon: StubComponent,
					VExpandTransition: StubComponent,
				},
			},
		});

		const moreToggle = wrapper.find('[data-test="drawer-more-toggle"]');
		expect(moreToggle.attributes("aria-expanded")).toBe("true");
		expect(moreToggle.text()).toContain("Show less");

		const secondaryCollapse = wrapper.find('[data-test="drawer-secondary-collapse"]');
		expect(secondaryCollapse.attributes("style") || "").not.toContain("display: none");
	});

	it("emits open-settings event when settings footer button is clicked", async () => {
		const onOpenSettings = vi.fn();
		const wrapper = mount(NavbarDrawer, {
			props: {
				drawer: true,
				company: "Radolfa",
				items: defaultItems,
				footerAction: {
					icon: "mdi-cog-outline",
					text: "Settings",
					subtitle: "Offline & terminal controls",
				},
				"onOpen-settings": onOpenSettings,
				onOpenSettings: onOpenSettings,
			},
			global: {
				components: {
					VNavigationDrawer: StubComponent,
					VAvatar: StubComponent,
					VImg: StubComponent,
					VDivider: StubComponent,
					VList: StubComponent,
					VListItem: StubComponent,
					VListItemTitle: StubComponent,
					VIcon: StubComponent,
					VExpandTransition: StubComponent,
				},
			},
		});

		const footerButton = wrapper.find('[data-test="drawer-footer-action"]');
		expect(footerButton.exists()).toBe(true);
		expect(footerButton.text()).toContain("Settings");

		await footerButton.trigger("click");
		expect(onOpenSettings).toHaveBeenCalled();
	});
});
