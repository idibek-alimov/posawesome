export function actualAmount(
	value: unknown,
	precision?: number,
): number | null {
	if (value === null || value === undefined || String(value).trim() === "")
		return null;
	const amount = Number(value);
	if (!Number.isFinite(amount)) return null;
	if (precision !== undefined) {
		const scaled = amount * 10 ** precision;
		if (
			!Number.isSafeInteger(Math.round(scaled)) ||
			Math.abs(scaled - Math.round(scaled)) >
				Math.max(1, Math.abs(scaled)) * Number.EPSILON * 2
		)
			return null;
	}
	return amount;
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

export function hasClosingDifference(rows: any[], precision = 3): boolean {
	return rows.some((row) => {
		const difference = closingDifference(row, precision);
		return difference !== null && difference !== 0;
	});
}
