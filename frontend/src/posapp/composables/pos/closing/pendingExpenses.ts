/** Shared request storage is evidence of an unknown result, never an offline posting queue. */
export function hasPendingExpenseRequest(
	shift?: string,
	company?: string,
): boolean {
	const actor = globalThis.frappe?.session?.user;
	if (!actor || typeof localStorage === "undefined") return false;
	return ["record_quick_expense", "cancel_quick_expense"].some((action) => {
		const key = `quick-expense:${actor}:${action}`;
		const saved =
			localStorage.getItem(key) ||
			(typeof sessionStorage !== "undefined"
				? sessionStorage.getItem(key)
				: null);
		if (!saved) return false;
		try {
			const pending = JSON.parse(saved);
			if (
				pending.args?.company &&
				company &&
				pending.args.company !== company
			)
				return false;
			if (pending.args?.pos_opening_shift)
				return !shift || pending.args.pos_opening_shift === shift;
			// A cancellation with incomplete local context may affect this shift.
			return (
				action === "cancel_quick_expense" || !!pending.args?.pos_profile
			);
		} catch {
			return true;
		}
	});
}
