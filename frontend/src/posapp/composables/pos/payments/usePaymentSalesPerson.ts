import { computed, type Ref } from "vue";
import { resolveSalesPerson } from "../../../utils/salesTeam";

/** Hydration is a pure read. Only a selection event replaces the recorded team. */
export function usePaymentSalesPerson(invoiceDoc: Ref<any>) {
	return computed({
		get: () => resolveSalesPerson(invoiceDoc.value),
		set: (value: string | null) => {
			const doc = invoiceDoc.value;
			if (!doc) return;
			doc.custom_sales_person = value || "";
			doc.sales_person = value || "";
			doc.sales_team = value
				? [{ sales_person: value, allocated_percentage: 100 }]
				: [];
		},
	});
}
