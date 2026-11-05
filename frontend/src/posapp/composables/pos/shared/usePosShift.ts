import { ref, getCurrentInstance, inject } from "vue";
import { useToastStore } from "../../../stores/toastStore.js";
import { useUIStore } from "../../../stores/uiStore.js";
import { useInvoiceStore } from "../../../stores/invoiceStore";
import {
	startupInitPromise,
	initPromise,
	getQueuedPayloadCount,
	checkDbHealth,
	getOpeningStorage,
	setOpeningStorage,
	clearOpeningStorage,
	setTaxTemplate,
	isOffline,
	getBootstrapSnapshot,
	setBootstrapSnapshot,
} from "../../../../offline/index";
import { getValidCachedOpeningForCurrentUser } from "../../../utils/openingCache";
import { createBootstrapSnapshotFromRegisterData } from "../../../../offline/bootstrapSnapshot";
import {
	finishStartupPhase,
	startStartupPhase,
} from "../../../../utils/startupTrace";
import { useFiscalPrinter } from "../payments/useFiscalPrinter";

declare const __BUILD_VERSION__: string;
declare const frappe: any;

type SkippedPrintedInvoice = {
	invoice?: string;
	doctype?: string;
	return_against?: string;
};

type ClosingShiftPreparationResponse = {
	closing_shift?: any;
	skipped_printed_invoices?: SkippedPrintedInvoice[];
	overview?: any;
};

const translateMessage = (value: string) =>
	typeof window !== "undefined" && window.__ ? window.__(value) : value;

export function buildSkippedClosingInvoicesPrompt(
	skippedInvoices: SkippedPrintedInvoice[],
) {
	const count = skippedInvoices.length;
	const baseMessage =
		count === 1
			? "1 printed return invoice references a cancelled invoice and will be excluded from closing."
			: `${count} printed return invoices reference cancelled invoices and will be excluded from closing.`;
	const details = skippedInvoices
		.slice(0, 5)
		.map((invoice) => {
			const invoiceName =
				invoice?.invoice || translateMessage("Unknown invoice");
			const returnAgainst = invoice?.return_against;
			return returnAgainst
				? `${invoiceName} (${translateMessage("Return Against")}: ${returnAgainst})`
				: invoiceName;
		})
		.join(", ");
	const detailMessage = details
		? `${translateMessage("Invoices")}: ${details}.`
		: "";
	return [
		translateMessage(baseMessage),
		detailMessage,
		translateMessage("The skipped invoice will remain a draft."),
		translateMessage("Do you want to proceed?"),
	]
		.filter(Boolean)
		.join(" ");
}

function normalizeClosingShiftPreparationResponse(
	payload: any,
): ClosingShiftPreparationResponse {
	if (payload?.closing_shift || payload?.skipped_printed_invoices) {
		return payload;
	}

	return {
		closing_shift: payload,
		skipped_printed_invoices: [],
	};
}

export function usePosShift(openDialog?: () => void) {
	const instance = getCurrentInstance();
	const proxy: any = instance?.proxy;
	const eventBus: any = proxy?.eventBus || inject("eventBus");
	const buildVersion =
		typeof __BUILD_VERSION__ !== "undefined" ? __BUILD_VERSION__ : null;
	const toastStore = useToastStore();
	const uiStore = useUIStore();

	const pos_profile = ref<any>(null);
	const pos_opening_shift = ref<any>(null);

	function applyRegisterData(data: any) {
		if (!data) {
			return;
		}
		pos_profile.value = data.pos_profile;
		pos_opening_shift.value = data.pos_opening_shift;
		uiStore.setRegisterData(data);
		setBootstrapSnapshot(
			createBootstrapSnapshotFromRegisterData(
				data,
				getBootstrapSnapshot(),
				{ buildVersion },
			),
		);

		try {
			frappe.realtime.emit("pos_profile_registered");
		} catch (e) {
			console.warn("Realtime emit failed", e);
		}
	}

	async function check_opening_entry() {
		const phase = startStartupPhase("pos_profile_and_settings_loading");
		await startupInitPromise;
		await checkDbHealth();
		const cachedOpening = getValidCachedOpeningForCurrentUser(
			getOpeningStorage(),
			frappe?.session?.user,
		);
		if (cachedOpening) {
			applyRegisterData(cachedOpening);
			console.info("LoadPosProfile (bootstrapped from cache)");
		}
		return frappe
			.call("posawesome.posawesome.api.shifts.check_opening_shift", {
				user: frappe.session.user,
			})
			.then((r: any) => {
				if (r.message) {
					applyRegisterData(r.message);
					if (pos_profile.value.taxes_and_charges) {
						frappe.call({
							method: "frappe.client.get",
							args: {
								doctype: "Sales Taxes and Charges Template",
								name: pos_profile.value.taxes_and_charges,
							},
							callback: (res: any) => {
								if (res.message) {
									setTaxTemplate(
										pos_profile.value.taxes_and_charges,
										res.message,
									);
								}
							},
						});
					}
					console.info("LoadPosProfile");
					finishStartupPhase(phase, "ok", {
						profile: pos_profile.value?.name || null,
						source: "server",
					});
					try {
						setOpeningStorage(r.message);
					} catch (e) {
						console.error("Failed to cache opening data", e);
					}
				} else {
					console.info("No opening shift found, opening dialog");
					clearOpeningStorage();
					openDialog && openDialog();
					finishStartupPhase(phase, "ok", {
						profile: null,
						source: "server_no_opening",
					});
				}
			})
			.catch((err: unknown) => {
				console.error("Error checking opening entry", err);
				const data =
					cachedOpening ||
					getValidCachedOpeningForCurrentUser(
						getOpeningStorage(),
						frappe?.session?.user,
					);
				if (data) {
					applyRegisterData(data);
					console.info("LoadPosProfile (cached)");
					finishStartupPhase(phase, "ok", {
						profile: pos_profile.value?.name || null,
						source: "cache_fallback",
					});
					return;
				}
				if (!isOffline()) {
					clearOpeningStorage();
				}
				openDialog && openDialog();
				finishStartupPhase(phase, "error", { error: err });
			});
	}

	let closingSubmission = false;
	async function closingQueuesReady() {
		await initPromise;
		if (
			isOffline() ||
			["invoice", "payment", "cash_movement"].some((entity: any) =>
				getQueuedPayloadCount(entity),
			)
		) {
			toastStore.show({
				title: translateMessage(
					"Sync pending invoices, payments and cash movements before closing the shift.",
				),
				color: "warning",
			});
			return false;
		}
		return true;
	}

	async function get_closing_data() {
		if (!(await closingQueuesReady())) return;
		const cachedOpeningShift = (getOpeningStorage() as any)
			?.pos_opening_shift;
		const resolvedShift =
			uiStore.posOpeningShift ||
			pos_opening_shift.value ||
			cachedOpeningShift ||
			null;
		if (!resolvedShift) {
			return Promise.resolve();
		}
		return frappe
			.call(
				"posawesome.posawesome.doctype.pos_closing_shift.pos_closing_shift.make_closing_shift_from_opening",
				{ opening_shift: resolvedShift },
			)
			.then((r: any) => {
				if (r.message) {
					const response = normalizeClosingShiftPreparationResponse(
						r.message,
					);
					const closingShift = response.closing_shift;
					const skippedPrintedInvoices = Array.isArray(
						response.skipped_printed_invoices,
					)
						? response.skipped_printed_invoices
						: [];
					if (!closingShift) {
						return;
					}

					if (skippedPrintedInvoices.length) {
						const confirmed = window.confirm(
							buildSkippedClosingInvoicesPrompt(
								skippedPrintedInvoices,
							),
						);
						if (!confirmed) {
							return;
						}
					}

					eventBus?.emit("open_ClosingDialog", {
						...closingShift,
						__overview: response.overview,
						skipped_printed_invoices: skippedPrintedInvoices,
					});
				}
			});
	}

	async function submit_closing_pos(data: any) {
		if (closingSubmission) return false;
		closingSubmission = true;
		try {
			if (!(await closingQueuesReady())) {
				eventBus?.emit("closing_shift_failed");
				return false;
			}
			const {
				print_z_report,
				transfer_to_safe,
				skipped_printed_invoices: _skipped,
				__overview: _overview,
				...closingData
			} = data;
			const r: any = await frappe.call(
				"posawesome.posawesome.doctype.pos_closing_shift.pos_closing_shift.submit_closing_shift",
				{ closing_shift: JSON.stringify(closingData) },
			);
			const closingShiftName =
				r.message?.name ||
				(typeof r.message === "string" ? r.message : "");
			if (!closingShiftName)
				throw new Error("Missing closing shift response");

			// Fiscal close and cash transfer follow a successful ERP closing only.
			if (print_z_report) {
				try {
					const fiscal = useFiscalPrinter();
					const cashierName =
						frappe.session?.user_fullname ||
						frappe.session?.user ||
						"";
					const printed = await fiscal.printZReport(cashierName);
					toastStore.show({
						title: translateMessage(
							printed
								? "Fiscal Z report printed."
								: "Shift closed, but the fiscal Z report was not printed.",
						),
						color: printed ? "success" : "warning",
					});
				} catch {
					toastStore.show({
						title: translateMessage(
							"Shift closed, but the fiscal Z report was not printed.",
						),
						color: "warning",
					});
				}
			}
			if (transfer_to_safe) {
				try {
					const transferRes: any = await frappe.call(
						"posawesome.posawesome.api.fiscal.transfer_shift_cash_to_safe",
						{ pos_closing_shift_name: closingShiftName },
					);
					const result = transferRes?.message;
					toastStore.show({
						title:
							result?.message ||
							translateMessage(
								"Shift closed, but cash was not transferred to the safe.",
							),
						color: result?.success ? "success" : "warning",
					});
				} catch {
					toastStore.show({
						title: translateMessage(
							"Shift closed, but cash was not transferred to the safe.",
						),
						color: "warning",
					});
				}
			}
			pos_profile.value = null;
			pos_opening_shift.value = null;
			uiStore.posOpeningShift = null;
			clearOpeningStorage();
			useInvoiceStore().clear();
			eventBus?.emit("closing_shift_submitted", {
				name: closingShiftName,
			});
			toastStore.show({
				title: translateMessage("POS Shift Closed"),
				color: "success",
			});
			check_opening_entry();
			return true;
		} catch (err) {
			console.error("Failed to submit closing shift", err);
			eventBus?.emit("closing_shift_failed");
			toastStore.show({
				title: translateMessage(
					"Could not close the shift. Check the error and refresh the totals before retrying.",
				),
				color: "error",
			});
			return false;
		} finally {
			closingSubmission = false;
		}
	}

	return {
		pos_profile,
		pos_opening_shift,
		check_opening_entry,
		get_closing_data,
		submit_closing_pos,
	};
}
