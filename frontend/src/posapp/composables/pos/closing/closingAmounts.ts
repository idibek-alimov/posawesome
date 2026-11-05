export function actualAmount(value: unknown): number | null {
	if (value === null || value === undefined || String(value).trim() === "")
		return null;
	const amount = Number(value);
	return Number.isFinite(amount) ? amount : null;
}

export function closingDifference(row: any, precision = 3): number | null {
	const actual = actualAmount(row?.closing_amount);
	if (actual === null) return null;
	// Match ERPNext's saved convention: negative means a shortage.
	return (
		Math.round(
			(actual - Number(row.expected_amount || 0)) * 10 ** precision,
		) /
		10 ** precision
	);
}
