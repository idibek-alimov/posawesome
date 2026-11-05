import { ref } from "vue";
import { actualAmount } from "./closingAmounts";

declare const frappe: any;

export function useClosingShift(eventBus: any) {
	const closingDialog = ref(false);
	const dialog_data = ref<any>({});
	const overview = ref<any>(null);
	const overviewLoading = ref(false);
	const overviewError = ref("");
	const submitting = ref(false);
	let requestId = 0;
	const pos_profile = ref("");

	const closeDialog = () => {
		if (submitting.value) return;
		requestId += 1;
		closingDialog.value = false;
		overview.value = null;
		overviewLoading.value = false;
	};

	const fetchOverview = (
		openingShift: string,
		posProfileCurrency: string,
		initialOverview?: any,
	) => {
		const currentRequest = ++requestId;
		overviewError.value = "";
		overviewLoading.value = true;
		overview.value = null;
		if (!openingShift) {
			overviewLoading.value = false;
			return;
		}

		const toNumber = (value: unknown) => {
			const number = Number(value);
			return Number.isFinite(number) ? number : 0;
		};

		const normalizeRates = (rates: unknown) => {
			if (Array.isArray(rates)) {
				return rates
					.map((rate) => Number(rate))
					.filter((rate) => Number.isFinite(rate) && rate > 0);
			}
			if (rates === null || rates === undefined || rates === "") {
				return [];
			}
			const numeric = Number(rates);
			return Number.isFinite(numeric) && numeric > 0 ? [numeric] : [];
		};

		const normalizeCurrencyRows = (value: unknown, options: any = {}) => {
			if (!Array.isArray(value)) {
				return [];
			}

			const { includeCount = false, includeExchangeRates = false } =
				options;

			return value.map((row: any) => {
				const record: any = {
					currency: row?.currency || "",
					total: toNumber(row?.total),
					company_currency_total: toNumber(
						row?.company_currency_total,
					),
					exchange_rates: includeExchangeRates
						? normalizeRates(row?.exchange_rates)
						: [],
				};

				if (includeCount) {
					record.invoice_count = toNumber(row?.invoice_count);
				}

				return record;
			});
		};

		const normalizePayments = (value: unknown) => {
			if (!Array.isArray(value)) {
				return [];
			}

			return value.map((row: any) => ({
				mode_of_payment: row?.mode_of_payment || "",
				currency: row?.currency || "",
				total: toNumber(row?.total),
				company_currency_total: toNumber(row?.company_currency_total),
				exchange_rates: normalizeRates(row?.exchange_rates),
			}));
		};

		const normalizeCredit = (credit: any = {}) => ({
			count: toNumber(credit?.count),
			company_currency_total: toNumber(credit?.company_currency_total),
			by_currency: normalizeCurrencyRows(credit?.by_currency, {
				includeCount: true,
				includeExchangeRates: true,
			}),
		});

		const normalizeLoyaltyRedemption = (loyalty: any = {}) => ({
			count: toNumber(loyalty?.count),
			points: toNumber(loyalty?.points),
			company_currency_total: toNumber(loyalty?.company_currency_total),
			by_currency: normalizeCurrencyRows(loyalty?.by_currency, {
				includeCount: true,
				includeExchangeRates: true,
			}).map((row: any, index: number) => ({
				...row,
				points: toNumber(loyalty?.by_currency?.[index]?.points),
			})),
		});

		const normalizeChangeReturned = (change: any = {}) => {
			const normalizeBranch = (branch: any = {}) => ({
				company_currency_total: toNumber(
					branch?.company_currency_total,
				),
				by_currency: normalizeCurrencyRows(branch?.by_currency, {
					includeExchangeRates: true,
				}),
			});

			const invoiceChange = normalizeBranch(
				change?.invoice_change || change || {},
			);
			const overpaymentChange = normalizeBranch(
				change?.overpayment_change || {},
			);

			const primaryByCurrency = normalizeCurrencyRows(
				change?.by_currency,
				{
					includeExchangeRates: true,
				},
			);

			const totalCompanyCurrencyValue = change?.company_currency_total;
			const totalCompanyCurrency = toNumber(totalCompanyCurrencyValue);
			const derivedTotalCompanyCurrency =
				invoiceChange.company_currency_total +
				overpaymentChange.company_currency_total;
			const hasTotalCompanyCurrency =
				totalCompanyCurrencyValue !== undefined &&
				totalCompanyCurrencyValue !== null &&
				totalCompanyCurrencyValue !== "";

			return {
				company_currency_total: hasTotalCompanyCurrency
					? totalCompanyCurrency
					: derivedTotalCompanyCurrency,
				by_currency: primaryByCurrency.length
					? primaryByCurrency
					: invoiceChange.by_currency,
				invoice_change: invoiceChange,
				overpayment_change: overpaymentChange,
			};
		};

		const normalizeCashMovements = (movements: any = {}) => ({
			count: toNumber(movements?.count),
			company_currency_total: toNumber(movements?.company_currency_total),
			by_currency: normalizeCurrencyRows(movements?.by_currency, {
				includeExchangeRates: true,
			}),
			by_type: Array.isArray(movements?.by_type)
				? movements.by_type.map((row: any) => ({
						movement_type: row?.movement_type || "",
						total: toNumber(row?.total),
					}))
				: [],
		});

		const normalize = (payload: any = {}) => ({
			reconciliation: payload.reconciliation,
			salespeople: payload.salespeople || [],
			movements: payload.movements || [],
			total_invoices: toNumber(payload.total_invoices),
			company_currency:
				payload.company_currency || posProfileCurrency || "",
			company_currency_total: toNumber(payload.company_currency_total),
			multi_currency_totals: normalizeCurrencyRows(
				payload.multi_currency_totals,
				{
					includeCount: true,
					includeExchangeRates: true,
				},
			),
			payments_by_mode: normalizePayments(payload.payments_by_mode),
			credit_invoices: normalizeCredit(payload.credit_invoices),
			sales_summary: {
				gross_company_currency_total: toNumber(
					payload.sales_summary?.gross_company_currency_total,
				),
				net_company_currency_total: toNumber(
					payload.sales_summary?.net_company_currency_total ??
						payload.company_currency_total,
				),
				average_invoice_value: toNumber(
					payload.sales_summary?.average_invoice_value,
				),
				sale_invoices_count: toNumber(
					payload.sales_summary?.sale_invoices_count,
				),
			},
			returns: {
				count: toNumber(payload.returns?.count),
				company_currency_total: toNumber(
					payload.returns?.company_currency_total,
				),
				by_currency: normalizeCurrencyRows(
					payload.returns?.by_currency,
					{
						includeCount: true,
						includeExchangeRates: true,
					},
				),
			},
			change_returned: normalizeChangeReturned(payload.change_returned),
			loyalty_redemption: normalizeLoyaltyRedemption(
				payload.loyalty_redemption,
			),
			customer_credit_redeemed: normalizeCredit(
				payload.customer_credit_redeemed,
			),
			cash_expected: {
				mode_of_payment: payload.cash_expected?.mode_of_payment || "",
				company_currency_total: toNumber(
					payload.cash_expected?.company_currency_total,
				),
				by_currency: normalizeCurrencyRows(
					payload.cash_expected?.by_currency,
					{
						includeExchangeRates: true,
					},
				),
			},
			cash_movements: normalizeCashMovements(payload.cash_movements),
		});

		const applyOverview = (payload: any) => {
			if (
				!payload ||
				!Array.isArray(payload.reconciliation) ||
				!payload.company_currency
			) {
				throw new Error("Incomplete closing summary");
			}
			if (currentRequest !== requestId) return;
			const previous = new Map(
				(dialog_data.value.payment_reconciliation || []).map(
					(row: any) => [row.mode_of_payment, row.closing_amount],
				),
			);
			dialog_data.value.payment_reconciliation =
				payload.reconciliation.map((row: any) => ({
					...row,
					closing_amount: previous.get(row.mode_of_payment) ?? "",
				}));
			overview.value = normalize(payload);
		};
		const onError = () => {
			if (currentRequest !== requestId) return;
			overview.value = null;
			overviewError.value =
				"Could not load shift totals. Try again before closing.";
		};
		if (initialOverview) {
			try {
				applyOverview(initialOverview);
			} catch {
				onError();
			}
			overviewLoading.value = false;
			return;
		}
		return Promise.resolve()
			.then(() =>
				frappe.call(
					"posawesome.posawesome.doctype.pos_closing_shift.pos_closing_shift.make_closing_shift_from_opening",
					{ opening_shift: { name: openingShift } },
				),
			)
			.then((r: any) => {
				const previous = dialog_data.value.payment_reconciliation;
				if (currentRequest !== requestId) return;
				if (!r?.message?.closing_shift)
					throw new Error("Missing closing draft");
				dialog_data.value = {
					...r.message.closing_shift,
					payment_reconciliation: previous,
					skipped_printed_invoices:
						r.message.skipped_printed_invoices || [],
				};
				applyOverview(r.message.overview);
			})
			.catch(onError)
			.finally(() => {
				if (currentRequest === requestId) overviewLoading.value = false;
			});
	};

	const submitDialog = (extraData: any = {}) => {
		if (
			submitting.value ||
			overviewLoading.value ||
			overviewError.value ||
			!overview.value
		)
			return false;
		const payments = dialog_data.value.payment_reconciliation || [];
		if (
			payments.some(
				(row: any) => actualAmount(row.closing_amount) === null,
			)
		)
			return false;
		submitting.value = true;
		overviewError.value = "";
		eventBus?.emit("submit_closing_pos", {
			...dialog_data.value,
			...extraData,
		});
		return true;
	};

	return {
		closingDialog,
		dialog_data,
		overview,
		overviewLoading,
		overviewError,
		submitting,
		pos_profile,
		closeDialog,
		fetchOverview,
		submitDialog,
	};
}
