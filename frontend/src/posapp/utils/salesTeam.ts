/** Copy source attribution without rounding shares or inventing missing percentages.
 * Native validation owns percentage totals; a legacy single-person field is used
 * only when no recorded team exists. Never carry original allocated amounts to a return.
 */
export function copySalesTeam(source: any): any[] {
	return Array.isArray(source)
		? source.map((row: any) => ({
				sales_person: row?.sales_person,
				allocated_percentage: row?.allocated_percentage,
			}))
		: [];
}

export function resolveSalesPerson(doc: any): string {
	return (
		doc?.sales_team?.[0]?.sales_person ||
		doc?.custom_sales_person ||
		doc?.sales_person ||
		""
	);
}
