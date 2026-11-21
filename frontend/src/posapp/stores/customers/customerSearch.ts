import type { CustomerSummary } from "../../types/models";

type SearchableCustomer = CustomerSummary & {
	_search_text?: string;
};

export function normalizeCustomerSearchTerm(
	term: string | null | undefined,
): string {
	if (typeof term !== "string") {
		return "";
	}
	return term.trim();
}

export function normalizeCustomerMobile(
	value: string | null | undefined,
): string {
	return String(value ?? "").replace(/\D/g, "");
}

export function isCustomerMobileSearchTerm(
	term: string | null | undefined,
): boolean {
	const normalized = normalizeCustomerSearchTerm(term);
	return Boolean(normalized) && /^[\d\s()+.-]+$/.test(normalized);
}

export function buildCustomerMobileSearchKeys(
	value: string | null | undefined,
): string[] {
	const digits = normalizeCustomerMobile(value);
	if (!digits) {
		return [];
	}

	const keys = new Set([digits]);
	if (digits.startsWith("00") && digits.length > 2) {
		keys.add(digits.slice(2));
	}
	if (digits.startsWith("0") && digits.length > 1) {
		keys.add(digits.slice(1));
	}
	for (const tailLength of [10, 9, 8]) {
		if (digits.length > tailLength) {
			keys.add(digits.slice(-tailLength));
		}
	}

	return Array.from(keys).filter((key) => key.length >= 4);
}

export function customerMobileMatchesSearch(
	mobile: string | null | undefined,
	term: string | null | undefined,
): boolean {
	const customerKeys = buildCustomerMobileSearchKeys(mobile);
	const searchKeys = buildCustomerMobileSearchKeys(term);
	return searchKeys.some((searchKey) =>
		customerKeys.some(
			(customerKey) =>
				customerKey.includes(searchKey) ||
				searchKey.includes(customerKey),
		),
	);
}

export function buildCustomerSearchParts(
	term: string | null | undefined,
): string[] {
	return normalizeCustomerSearchTerm(term)
		.toLowerCase()
		.split(/\s+/)
		.filter(Boolean);
}

export function buildCustomerSearchText(
	customer: CustomerSummary | null | undefined,
): string {
	if (!customer) {
		return "";
	}

	return [
		customer.customer_name,
		customer.name,
		customer.mobile_no,
		customer.email_id,
		(customer as CustomerSummary & { tax_id?: unknown }).tax_id,
		customer.posa_barcode,
		normalizeCustomerMobile(customer.mobile_no),
	]
		.filter((value) => value !== null && value !== undefined)
		.map((value) => String(value).toLowerCase())
		.join("\n");
}

export function normalizeCustomerBarcode(
	value: string | null | undefined,
): string {
	return String(value ?? "")
		.trim()
		.toLowerCase();
}

export function customerBarcodeMatchesSearch(
	barcode: string | null | undefined,
	term: string | null | undefined,
): boolean {
	const normalizedBarcode = normalizeCustomerBarcode(barcode);
	const normalizedTerm = normalizeCustomerBarcode(term);
	if (!normalizedBarcode || !normalizedTerm) {
		return false;
	}
	return normalizedBarcode.includes(normalizedTerm);
}

export function isExactCustomerBarcodeMatch(
	customer: CustomerSummary | null | undefined,
	term: string | null | undefined,
): boolean {
	if (!customer) {
		return false;
	}
	const normalizedBarcode = normalizeCustomerBarcode(customer.posa_barcode);
	const normalizedTerm = normalizeCustomerBarcode(term);
	return Boolean(
		normalizedBarcode &&
			normalizedTerm &&
			normalizedBarcode === normalizedTerm,
	);
}

export function customerMatchesSearchParts(
	customer: CustomerSummary | null | undefined,
	searchParts: readonly string[],
): boolean {
	if (!searchParts.length) {
		return true;
	}

	if (!customer) {
		return false;
	}

	const searchableCustomer = customer as SearchableCustomer;
	const searchText =
		searchableCustomer._search_text || buildCustomerSearchText(customer);

	return searchParts.every((part) => searchText.includes(part));
}

export function customerMatchesSearchTerm(
	customer: CustomerSummary | null | undefined,
	term: string | null | undefined,
): boolean {
	if (isCustomerMobileSearchTerm(term)) {
		return (
			customerMobileMatchesSearch(customer?.mobile_no, term) ||
			customerBarcodeMatchesSearch(customer?.posa_barcode, term) ||
			customerMatchesSearchParts(customer, buildCustomerSearchParts(term))
		);
	}
	return customerMatchesSearchParts(customer, buildCustomerSearchParts(term));
}

export type CustomerDuplicateField =
	| "customer_name"
	| "mobile_no"
	| "posa_barcode"
	| "email_id"
	| "tax_id";

export function normalizeCustomerDuplicateValue(
	field: CustomerDuplicateField,
	value: unknown,
): string {
	const normalized = String(value ?? "")
		.trim()
		.toLowerCase();
	if (field === "mobile_no") {
		return normalized.replace(/\D/g, "");
	}
	if (field === "customer_name") {
		return normalized.replace(/\s+/g, " ");
	}
	if (field === "tax_id" || field === "posa_barcode") {
		return normalized.replace(/\s+/g, "");
	}
	return normalized;
}

export function getCustomerDuplicateFields(
	customer: CustomerSummary,
	candidate: Partial<CustomerSummary>,
	includeCustomerName = true,
): CustomerDuplicateField[] {
	const fields: CustomerDuplicateField[] = [
		...(includeCustomerName ? (["customer_name"] as const) : []),
		"mobile_no",
		"posa_barcode",
		"email_id",
		"tax_id",
	];
	return fields.filter((field) => {
		const candidateValue = normalizeCustomerDuplicateValue(
			field,
			candidate[field],
		);
		const customerValue = normalizeCustomerDuplicateValue(
			field,
			customer[field],
		);
		if (!candidateValue || !customerValue) {
			return false;
		}
		if (field === "mobile_no") {
			const candDigits =
				candidateValue.length >= 9
					? candidateValue.slice(-9)
					: candidateValue;
			const custDigits =
				customerValue.length >= 9
					? customerValue.slice(-9)
					: customerValue;
			return (
				candDigits === custDigits || candidateValue === customerValue
			);
		}
		return candidateValue === customerValue;
	});
}

export function generateCustomerCardBarcode(): string {
	// Generates a unique 13-digit internal EAN-13 loyalty card barcode (prefix "29")
	const timestampPart = String(Date.now()).slice(-7);
	const randomPart = String(Math.floor(100 + Math.random() * 900));
	const base12 = `29${timestampPart}${randomPart}`;
	let sum = 0;
	for (let i = 0; i < 12; i += 1) {
		const digit = Number(base12[i] || 0);
		sum += i % 2 === 0 ? digit : digit * 3;
	}
	const checkDigit = (10 - (sum % 10)) % 10;
	return `${base12}${checkDigit}`;
}

export function formatCustomerBirthdayDisplay(
	value: string | null | undefined,
): string {
	const raw = String(value ?? "").trim();
	if (!raw) {
		return "";
	}
	if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
		const [year, month, day] = raw.split("-");
		return `${day}.${month}.${year}`;
	}
	if (/^\d{2}[-./]\d{2}[-./]\d{4}$/.test(raw)) {
		return raw.replace(/[-/]/g, ".");
	}
	return raw;
}

export function isCustomerBirthdaySoon(
	value: string | null | undefined,
	windowDays = 3,
): { isToday: boolean; isSoon: boolean; displayDate: string } | null {
	const raw = String(value ?? "").trim();
	if (!raw) {
		return null;
	}
	let day = 0;
	let month = 0;
	if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
		const parts = raw.split("-");
		month = Number(parts[1]);
		day = Number(parts[2]);
	} else if (/^\d{1,2}[-./]\d{1,2}[-./]\d{4}$/.test(raw)) {
		const parts = raw.split(/[-./]/);
		day = Number(parts[0]);
		month = Number(parts[1]);
	}
	if (!day || !month || month < 1 || month > 12 || day < 1 || day > 31) {
		return null;
	}
	const now = new Date();
	const todayMidnight = new Date(
		now.getFullYear(),
		now.getMonth(),
		now.getDate(),
	);
	const bdayThisYear = new Date(now.getFullYear(), month - 1, day);
	const diffDays = Math.round(
		(bdayThisYear.getTime() - todayMidnight.getTime()) /
			(1000 * 60 * 60 * 24),
	);
	if (Math.abs(diffDays) <= windowDays) {
		return {
			isToday: diffDays === 0,
			isSoon: true,
			displayDate: `${String(day).padStart(2, "0")}.${String(month).padStart(2, "0")}`,
		};
	}
	return null;
}
