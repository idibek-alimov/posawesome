// Manager projection only: all allocations and posting use the Phase 6 service.
frappe.pages["shift-review"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Shift Review"), single_column: true });
	wrapper.shift_review_app = new ShiftReviewApp(page);
};
frappe.pages["shift-review"].on_page_show = function (wrapper) {
	wrapper.shift_review_app?.show();
};

class ShiftReviewApp {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body).addClass("shift-review-page");
		this.filters = {
			status: "unresolved",
			search: "",
			company: "",
			pos_profile: "",
			cashier: "",
			from_date: "",
			to_date: "",
		};
		this.sequence = 0;
		this.page.set_secondary_action(__("Refresh"), () => this.show());
		this.page.add_menu_item(__("Expenses"), () => frappe.set_route("expense-desk"));
		this.page.add_menu_item(__("Money Hub"), () => frappe.set_route("money-hub"));
		window.addEventListener("offline", () => {
			++this.sequence;
			this.ready = false;
			this.wrapper.html(`<p role="alert">${__("Offline. Reconnect to load shift reviews.")}</p>`);
			this.render_recovery();
		});
		window.addEventListener("online", () => this.show());
		this.wrapper.on("click", "a[href]", () => {
			this.return_refresh = true;
		});
		window.addEventListener("focus", () => {
			if (
				this.return_refresh &&
				frappe.get_route()[0] === "shift-review" &&
				!this.dialog &&
				!this.entry
			) {
				this.return_refresh = false;
				this.show();
			}
		});
		this.show();
	}
	esc(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}
	money(value, currency = this.detail?.currency, precision = this.detail?.currency_precision) {
		return this.esc(format_currency(value, currency, precision));
	}
	link(doctype, name, label = name) {
		return name
			? `<a href="${this.esc(frappe.utils.get_form_link(doctype, name))}">${this.esc(label)}</a>`
			: "—";
	}
	review_link(name, label) {
		return `<a href="/app/shift-review/${encodeURIComponent(name)}">${this.esc(label)}</a>`;
	}
	async call(method, args) {
		const response = await frappe.call({ method: `posawesome.posawesome.shift_review.${method}`, args });
		if (!response.message)
			throw new Error(__("The server result was not confirmed. Retry to check its status."));
		return response.message;
	}
	async show(more = false) {
		clearTimeout(this.search_timer);
		const name = frappe.get_route()[1];
		const sequence = ++this.sequence;
		this.ready = false;
		this.wrapper.attr("aria-busy", "true");
		const previous = more ? this.rows || [] : [];
		if (name || !this.wrapper.find(".sr-filters").length)
			this.wrapper.html(`<p role="status">${__("Loading…")}</p>`);
		else this.wrapper.find(".sr-summary, .sr-results").text(__("Loading…"));
		try {
			const data = name
				? await this.call("desk.get_detail", { review_name: decodeURIComponent(name) })
				: await this.call("desk.get_list", { ...this.filters, limit_start: previous.length });
			if (sequence !== this.sequence) return;
			this.ready = true;
			this.detail = name ? data : null;
			if (name) this.render_detail(data);
			else {
				this.rows = [...previous, ...data.rows];
				this.render_list(data);
			}
		} catch (error) {
			if (sequence !== this.sequence) return;
			this.wrapper.html(
				`<p role="alert">${this.esc(error.message || __("Could not load Shift Review. Check access and setup."))}</p><button class="btn btn-default" data-retry>${__("Retry")}</button>`,
			);
			this.wrapper.find("[data-retry]").on("click", () => this.show());
		} finally {
			if (sequence === this.sequence) {
				this.wrapper.attr("aria-busy", "false");
				this.render_recovery();
			}
		}
	}
	table(labels, rows) {
		return `<div class="sr-scroll" tabindex="0" role="region" aria-label="${this.esc(__(labels[0]))}"><table><thead><tr>${labels.map((label) => `<th>${this.esc(__(label))}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
	}
	render_list(data) {
		if (!this.wrapper.find(".sr-filters").length) {
			this.wrapper
				.html(`<div class="sr-workspace"><div class="sr-recovery" aria-live="polite"></div><div class="sr-summary" aria-live="polite"></div>
			<p class="text-muted">${__("Shift differences, not account balances. Unresolved reviews include all dates. Shortages and surpluses are kept separate.")}</p>
			<div class="sr-filters"><div data-control="company"></div><div data-control="pos_profile"></div><div data-control="cashier"></div>
			<label>${__("Status")}<select class="form-control" data-filter="status">${["unresolved", "Pending review", "In review", "Partially resolved", "Resolved", "Voided", "all"].map((value) => `<option value="${this.esc(value)}">${this.esc(__(value === "unresolved" ? "Unresolved · all dates" : value === "all" ? "All reviews" : value))}</option>`).join("")}</select></label>
			<label class="sr-search">${__("Search")}<input class="form-control" data-filter="search" type="search" placeholder="${this.esc(__("Shift, register or cashier"))}"></label></div>
			<details class="sr-dates"><summary>${__("Review dates for history")}</summary><div><label>${__("From date")}<input class="form-control" type="date" data-filter="from_date"></label><label>${__("To date")}<input class="form-control" type="date" data-filter="to_date"></label></div></details>
			<button class="btn btn-default btn-sm sr-reset">${__("Reset filters")}</button><div class="sr-results"></div><p class="sr-count text-muted"></p><button class="btn btn-default sr-more">${__("Load more")}</button></div>`);
			for (const [key, label, doctype] of [
				["company", "Company", "Company"],
				["pos_profile", "Register", "POS Profile"],
				["cashier", "Cashier", "User"],
			]) {
				const control = frappe.ui.form.make_control({
					parent: this.wrapper.find(`[data-control=${key}]`),
					df: {
						fieldname: key,
						label: __(label),
						fieldtype: "Link",
						options: doctype,
						onchange: () => {
							if (this.updating) return;
							this.filters[key] = control.get_value();
							this.show();
						},
					},
					render_input: true,
				});
				control.$input?.attr("aria-label", __(label));
				this.updating = true;
				control.set_input(this.filters[key]);
				this.updating = false;
			}
			for (const [key, value] of Object.entries(this.filters))
				this.wrapper.find(`[data-filter=${key}]`).val(value);
			this.wrapper.find("[data-filter]").on("input change", (event) => {
				const key = event.currentTarget.dataset.filter;
				this.filters[key] = event.currentTarget.value;
				clearTimeout(this.search_timer);
				// Invalidate in-flight requests immediately, including the debounce window.
				++this.sequence;
				this.ready = false;
				this.wrapper.find(".sr-summary, .sr-results").text(__("Loading…"));
				this.search_timer = setTimeout(() => this.show(), key === "search" ? 250 : 0);
			});
			this.wrapper.find(".sr-reset").on("click", () => {
				Object.keys(this.filters).forEach(
					(key) => (this.filters[key] = key === "status" ? "unresolved" : ""),
				);
				this.wrapper.empty();
				this.show();
			});
			this.wrapper.find(".sr-more").on("click", () => {
				if (this.ready) this.show(true);
			});
		}
		this.wrapper.find(".sr-dates").prop("hidden", !["Resolved", "Voided"].includes(this.filters.status));
		this.wrapper
			.find(".sr-summary")
			.html(
				`<div><span>${__("Shifts needing review")}</span><strong>${data.shifts_needing_review}</strong></div>${(data
					.currencies.length
					? data.currencies
					: [{ currency: "", shortage: "—", surplus: "—" }]
				)
					.map((row) =>
						["shortage", "surplus"]
							.map(
								(key) =>
									`<div><span>${__(key === "shortage" ? "Unresolved shortage" : "Unresolved surplus")}</span><strong>${row.currency ? this.money(row[key], row.currency) : "—"}</strong></div>`,
							)
							.join(""),
					)
					.join("")}`,
			);
		this.wrapper.find(".sr-results").html(
			this.rows.length
				? this.table(
						["Shift / date", "Cashier", "Account", "Unresolved amount", "Status"],
						this.rows.map(
							(row) => `<tr>
			<td>${this.review_link(row.name, row.closing_shift)}<small>${this.esc(row.pos_profile)} · ${this.esc(row.creation)}</small><small>${this.esc(row.company)}</small></td>
			<td>${this.esc(row.cashier)}</td><td>${this.esc(row.account || __("Missing account mapping"))}<small>${this.esc((row.methods || []).join(", "))}</small></td><td class="sr-amount">${this.money(row.remaining_amount, row.currency, row.currency_precision)}<small>${__(Number(row.remaining_amount) < 0 ? "Shortage" : Number(row.remaining_amount) > 0 ? "Surplus" : "Resolved")}</small></td><td>${this.esc(__(row.status))}</td></tr>`,
						),
					)
				: `<p class="sr-empty">${__("No matching reviews. Change the filters to view history.")}</p>`,
		);
		this.wrapper
			.find(".sr-count")
			.text(__("Showing {0} of {1} matching records", [this.rows.length, data.total]));
		this.wrapper.find(".sr-more").prop("hidden", !data.has_more);
	}
	render_detail(data) {
		const capabilities = data.capabilities;
		this.wrapper
			.html(`<div class="sr-workspace"><a href="/app/shift-review">${__("Back to reviews")}</a><div class="sr-recovery" aria-live="polite"></div>
		<h2>${this.esc(data.pos_profile)} · ${this.esc(data.closing_shift)}</h2><p>${this.esc(data.cashier)} · ${this.esc(data.period_start)} — ${this.esc(data.period_end)}</p>
		<p>${__(data.status === "Voided" ? "Cancelled closing" : "Closed shift")} · ${this.esc(__(data.status))} · ${this.esc(data.company)} · ${this.esc(data.currency)}</p>
		<p class="text-muted">${__("These are the original shift counts and valid explanations. They are not the current account balance.")}</p>
		${this.table(
			[
				"Account",
				"Expected",
				"Actual",
				"Original difference",
				"Explained / adjusted",
				"Remaining",
				"Review actions",
			],
			data.accounts.map((row) => {
				const allowed = capabilities.rows[row.row_key];
				return `<tr><td>${this.esc(row.account || __("Missing account mapping"))}<small>${this.esc((row.methods || []).join(", "))}</small></td>${["expected_amount", "actual_amount", "original_difference", "allocated_amount", "remaining_amount"].map((key) => `<td class="sr-amount">${this.money(row[key])}</td>`).join("")}<td class="sr-actions">${[
					["Link source", "Link existing transaction", allowed.link_source],
					["Missing expense", "Record missing expense", allowed.missing_expense],
					["Count correction", "Correct count", allowed.count_correction],
					["Cash adjustment", "Approve cash adjustment", allowed.cash_adjustment],
				]
					.filter((item) => item[2])
					.map(
						([action, label]) =>
							`<button class="btn btn-default btn-sm" data-action="${action}" data-row="${this.esc(row.row_key)}">${__(label)}</button>`,
					)
					.join(
						"",
					)}${allowed.adjustment_reason ? `<small>${this.esc(allowed.adjustment_reason)}</small>` : ""}</td></tr>`;
			}),
		)}
		<div class="sr-explanation"><h3>${__("Cashier explanation")}</h3><p>${this.esc(data.cashier_reason || __("No explanation recorded"))}</p><p>${__("Reviewer")}: ${this.esc(data.reviewer || "—")}</p></div>
		${capabilities.can_investigate ? `<div class="sr-actions"><button class="btn btn-default" data-action="Investigate">${__("Take review / add note")}</button><button class="btn btn-default" data-action="Payment correction request">${__("Request native correction")}</button><button class="btn btn-default" data-action="Confirm payment correction">${__("Verify payment amendment")}</button></div>` : ""}
		<p class="text-muted">${__("Bank, refund, transfer and recovery cases use permitted native documents. A request alone does not resolve money. Closed invoices retain their native correction restrictions.")}</p>
		<p>${["Payment Entry", "Journal Entry", "Expense Claim", "Purchase Invoice"]
			.filter((doctype) => (frappe.boot.user.can_read || []).includes(doctype))
			.map((doctype) => `<a href="/app/${frappe.router.slug(doctype)}">${this.esc(__(doctype))}</a>`)
			.join(" · ")}</p>
		<p class="text-muted">${__("If the cost is already recorded on a claim or supplier bill, pay that native document. Do not record the expense again here.")}</p>
		${capabilities.expense_setup_error ? `<p role="status">${this.esc(capabilities.expense_setup_error)}</p>` : ""}
		${capabilities.adjustment_setup_error ? `<p role="status">${this.esc(capabilities.adjustment_setup_error)}</p>` : ""}
		<details><summary>${__("Transactions")}</summary>${this.source_table(data.sources.filter((row) => !["Quick Expense", "POS Cash Movement"].includes(row.doctype)))}</details>
		<details><summary>${__("Expenses / transfers")}</summary>${this.source_table(data.sources.filter((row) => ["Quick Expense", "POS Cash Movement"].includes(row.doctype)))}</details>
		<details><summary>${__("Payment method counts")}</summary>${this.table(
			["Payment method", "Account", "Expected", "Actual", "Original difference"],
			data.methods.map(
				(row) =>
					`<tr><td>${this.esc(row.mode_of_payment)}</td><td>${this.esc(row.account)}</td>${["expected_amount", "actual", "difference"].map((key) => `<td class="sr-amount">${this.money(row[key])}</td>`).join("")}</tr>`,
			),
		)}</details>
		<h3>${__("Resolution history")}</h3>${
			data.history.length
				? this.table(
						["Date / reviewer", "Action", "Amount", "Evidence"],
						data.history.map(
							(item) =>
								`<tr><td>${this.esc(item.creation)}<small>${this.esc(item.actor)}</small></td><td>${this.esc(__(item.action))} · ${this.esc(__(item.state))}<small>${this.esc(item.reason)}</small>${item.invalidation_reason ? `<small role="status">${this.esc(item.invalidation_reason)}</small>` : ""}${item.count ? `<small>${this.esc(item.count.mode_of_payment)}: ${this.esc(item.count.previous_actual)} → ${this.esc(item.count.new_actual)}</small>` : ""}</td><td class="sr-amount">${this.money(item.signed_amount)}</td><td>${this.link(item.source_doctype, item.source_name)}${this.expense_link(item.source_doctype, item.source_name)}<small>${this.link(item.financial_doctype, item.financial_name)}</small>${item.state === "Requested" && capabilities.can_investigate ? `<button class="btn btn-default btn-sm" data-request="${this.esc(item.name)}" data-action="Confirm native handoff">${__("Attach native outcome")}</button><button class="btn btn-default btn-sm" data-request="${this.esc(item.name)}" data-action="Withdraw request">${__("Withdraw request")}</button>` : ""}${item.action === "Count correction" && item.state === "Complete" && capabilities.can_investigate ? `<button class="btn btn-default btn-sm" data-history="${this.esc(item.name)}" data-action="Withdraw count correction">${__("Withdraw count correction")}</button>` : ""}</td></tr>`,
						),
					)
				: `<p>${__("No review actions yet")}</p>`
		}
		<p>${this.link("POS Closing Shift", data.closing_shift, __("Open closing record"))} · ${this.link("POS Opening Shift", data.pos_opening_shift, __("Open opening record"))} · ${this.link("POS Shift Review", data.review, __("Open full review form (advanced)"))}</p></div>`);
		this.wrapper.find("[data-action]").on("click", (event) => {
			if (!this.ready) return;
			const target = event.currentTarget.dataset;
			this.open_action(target.action, target.row, target.request, target.history);
		});
		this.wrapper.find("[data-expense]").on("click", (event) => {
			const target = event.currentTarget.dataset;
			this.open_expense_detail(target.doctype, target.expense);
		});
	}
	async open_expense_detail(source_doctype, name) {
		const review = this.detail?.review;
		await frappe.require("/assets/erpnext/js/expense_entry.js");
		if (!this.ready || this.detail?.review !== review) return;
		const adapter = {
			mark_native_navigation: () => {
				this.return_refresh = true;
			},
			data: { currency: this.detail.currency },
			esc: this.esc.bind(this),
			money: this.money.bind(this),
			link: this.link.bind(this),
			category_label: (value) => value || "—",
			shift_links: frappe.expense_entry.shift_links,
			receipt_url: frappe.expense_entry.receipt_url,
		};
		return frappe.expense_entry.open_detail.call(adapter, { source_doctype, name });
	}
	expense_link(doctype, name) {
		return ["Quick Expense", "POS Cash Movement"].includes(doctype) && name
			? `<button class="btn btn-link btn-sm" data-doctype="${this.esc(doctype)}" data-expense="${this.esc(name)}">${__("Expense details")}</button>`
			: "";
	}
	source_table(rows) {
		return rows.length
			? this.table(
					["Source document", "Date", "Amount", "Current state"],
					rows.map((row) =>
						row.restricted
							? `<tr><td colspan="4">${__("Source restricted or unavailable")}</td></tr>`
							: `<tr><td>${this.link(row.doctype, row.name)}${this.expense_link(row.doctype, row.name)}<small>${this.esc(__(row.document?.movement_type || row.doctype))}</small></td><td>${this.esc(row.posting_date)}</td><td class="sr-amount">${row.amount != null ? this.money(row.amount) : "—"}${row.original_currency && row.original_currency !== this.detail.currency ? `<small>${this.esc(format_currency(row.original_amount, row.original_currency))}</small>` : ""}</td><td>${__(row.docstatus === 2 ? "Cancelled" : row.docstatus === 1 ? "Submitted" : "Draft")}${(row.financial || []).map((voucher) => (voucher.restricted ? `<small>${__("Accounting source restricted or unavailable")}</small>` : `<small>${this.link(voucher.doctype, voucher.name)} · ${__(voucher.reversed ? "Reversed" : voucher.docstatus === 2 ? "Cancelled" : voucher.docstatus === 1 ? "Submitted" : "Draft")}</small>`)).join("")}${row.changed ? `<small>${__("Changed since closing. Investigate the native record; the original snapshot is retained.")}</small>` : ""}</td></tr>`,
					),
				)
			: `<p>${__("No source records")}</p>`;
	}
	async open_action(action, row_key, request_action_name, action_name) {
		if (!this.ready || this.dialog || this.entry) return;
		let detail = this.detail;
		let row = detail.accounts.find((item) => item.row_key === row_key);
		if (action === "Missing expense") return this.open_expense(row, detail);
		const fields = [
			{
				fieldname: "effect",
				fieldtype: "HTML",
				options: `<p>${this.esc(detail.pos_profile)} · ${this.esc(detail.currency)}${row ? ` · ${this.esc(row.account)} · ${__("Remaining")}: ${this.money(row.remaining_amount)}` : ""}</p>`,
			},
		];
		let request_type;
		if (action === "Payment correction request") {
			request_type = true;
			fields.push({
				fieldname: "request_type",
				fieldtype: "Select",
				label: __("Correction route"),
				options: [
					"Payment correction request",
					"Refund request",
					"Transfer request",
					"Recovery request",
					"Bank reconciliation request",
				].map((value) => ({ value, label: __(value) })),
				reqd: 1,
			});
		}
		if (["Link source", "Confirm payment correction", "Confirm native handoff"].includes(action)) {
			fields.push(
				{
					fieldname: "source_doctype",
					fieldtype: "Select",
					label: __("Source type"),
					options: (action === "Confirm payment correction"
						? ["Sales Invoice", "POS Invoice"]
						: detail.capabilities.source_types
					).map((value) => ({ value, label: __(value) })),
					reqd: 1,
				},
				{
					fieldname: "source_name",
					fieldtype: "Dynamic Link",
					label: __("Source document"),
					options: "source_doctype",
					get_query: () => ({
						filters: {
							company: detail.company,
							docstatus: action === "Confirm native handoff" ? ["in", [1, 2]] : 1,
						},
					}),
					reqd: 1,
				},
			);
			if (action !== "Confirm payment correction")
				fields.push({
					fieldname: "attribute_to_shift",
					fieldtype: "Check",
					label: __("Attribute this source to this exact shift"),
					description: __(
						"Required for sources without a stored shift. Does not change the native document.",
					),
				});
		}
		if (["Link source", "Cash adjustment"].includes(action))
			fields.push({
				fieldname: "amount",
				fieldtype: "Currency",
				label: __("Amount to explain"),
				options: detail.currency,
				default: Math.abs(Number(row.remaining_amount)),
				reqd: 1,
			});
		if (action === "Cash adjustment") {
			fields.push(
				{
					fieldtype: "HTML",
					fieldname: "adjustment",
					options: `<p>${__("This posts a Journal Entry for money already missing or found. It does not make a physical payment.")}</p><p>${__("Counterpart account")}: ${this.esc(detail.capabilities.rows[row_key].adjustment_account)}</p>`,
				},
				{
					fieldname: "posting_date",
					fieldtype: "Date",
					label: __("Date"),
					default: frappe.datetime.get_today(),
					reqd: 1,
				},
			);
		}
		if (action === "Count correction")
			fields.push(
				{
					fieldname: "mode_of_payment",
					fieldtype: "Select",
					label: __("Payment method"),
					options: detail.methods
						.filter(
							(method) =>
								method.account === row.account &&
								Math.sign(Number(method.difference)) ===
									Math.sign(Number(row.original_difference)),
						)
						.map((method) => method.mode_of_payment),
					reqd: 1,
				},
				{
					fieldname: "new_actual",
					fieldtype: "Currency",
					label: __("Corrected actual count"),
					options: detail.currency,
					reqd: 1,
				},
			);
		fields.push(
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason / note"), reqd: 1 },
			{ fieldname: "result", fieldtype: "HTML" },
		);
		const dialog = (this.dialog = new frappe.ui.Dialog({
			title: __(action === "Link source" ? "Link existing transaction" : action),
			fields,
			primary_action_label: __("Review and confirm"),
			primary_action: async (values) => {
				if (dialog.busy) return;
				// A proven rollback permits rechecking fresh scope while retaining input.
				// Unknown requests keep their original version and immutable intent.
				let pending;
				try {
					pending = this.pending();
				} catch (error) {
					dialog.get_field("result").$wrapper.text(error.message);
					return;
				}
				if (!pending && this.detail?.review === detail.review) {
					detail = this.detail;
					row = detail.accounts.find((item) => item.row_key === row_key);
				}
				const args = { ...values, row_key, request_action_name, action_name };
				if (action === "Cash adjustment")
					args.expected_adjustment_account = detail.capabilities.rows[row_key].adjustment_account;
				delete args.request_type;
				delete args.amount;
				if (["Link source", "Cash adjustment"].includes(action)) {
					if (
						!Number.isFinite(Number(values.amount)) ||
						Number(values.amount) <= 0 ||
						Number(values.amount) > Math.abs(Number(row.remaining_amount))
					)
						return frappe.msgprint(
							__("Enter a positive amount no greater than the remaining difference."),
						);
					args.signed_amount = Math.sign(Number(row.remaining_amount)) * Number(values.amount);
				}
				dialog.busy = true;
				dialog.get_primary_btn().prop("disabled", true);
				try {
					const selected = request_type ? values.request_type : action;
					let effect = `${__(selected)} · ${detail.closing_shift}${row ? ` · ${row.account}` : ""}${values.amount ? ` · ${values.amount} ${detail.currency}` : ""}${values.source_name ? ` · ${values.source_doctype}: ${values.source_name}` : ""}${action === "Count correction" ? ` · ${values.mode_of_payment}: ${values.new_actual} ${detail.currency}` : ""}${values.posting_date ? ` · ${values.posting_date}` : ""}${action === "Cash adjustment" ? ` · ${detail.capabilities.rows[row_key].adjustment_account}` : ""}`;
					if (action === "Cash adjustment") {
						const counterpart = detail.capabilities.rows[row_key].adjustment_account;
						const debit = Number(row.remaining_amount) < 0 ? counterpart : row.account;
						const credit = Number(row.remaining_amount) < 0 ? row.account : counterpart;
						effect += ` · ${__("Debit")}: ${debit} · ${__("Credit")}: ${credit}`;
					}
					if (args.signed_amount)
						effect += ` · ${__("Remaining after explanation")}: ${Number(row.remaining_amount) - args.signed_amount} ${detail.currency}`;
					if (!(await this.confirm(effect))) return;
					await this.execute(selected, args, detail);
					dialog.hide();
					await this.show();
				} catch (error) {
					dialog
						.get_field("result")
						.$wrapper.text(
							[
								error.message,
								__(
									"Action failed. Inputs are retained. Refresh before retrying a changed review.",
								),
							]
								.filter(Boolean)
								.join(" "),
						);
					await this.show();
				} finally {
					dialog.busy = false;
					dialog.get_primary_btn().prop("disabled", false);
					this.render_recovery();
				}
			},
		}));
		dialog.onhide = () => {
			if (this.dialog === dialog) this.dialog = null;
		};
		dialog.show();
	}
	confirm(message) {
		return new Promise((resolve) =>
			frappe.confirm(
				this.esc(message),
				() => resolve(true),
				() => resolve(false),
			),
		);
	}
	pending_key() {
		return `pos-shift-review:${frappe.session.user}`;
	}
	pending() {
		try {
			const raw = localStorage.getItem(this.pending_key());
			if (!raw) return null;
			const pending = JSON.parse(raw);
			if (
				!pending?.id ||
				!pending.intent?.review_name ||
				!pending.intent.action ||
				!pending.intent.args ||
				pending.intent.expected_version == null
			)
				throw new Error("Invalid saved intent");
			return pending;
		} catch {
			throw new Error(
				__(
					"Saved review evidence cannot be read. Ask a manager to investigate before posting again.",
				),
			);
		}
	}
	async execute(action, args, detail) {
		if (navigator.onLine === false) throw new Error(__("Offline. Reconnect to load shift reviews."));
		const intent = JSON.parse(
			JSON.stringify({ review_name: detail.review, action, args, expected_version: detail.version }),
		);
		let pending = this.pending();
		if (pending && JSON.stringify(pending.intent) !== JSON.stringify(intent))
			throw new Error(
				__("An earlier review request needs confirmation. Check or retry its saved result first."),
			);
		if (!pending) {
			pending = { id: crypto.randomUUID(), intent };
			// Persist before sending; storage failure must prevent an unsafe financial send.
			localStorage.setItem(this.pending_key(), JSON.stringify(pending));
		}
		try {
			const result = await this.call("service.act", {
				...pending.intent,
				client_request_id: pending.id,
			});
			if (!result.operation || result.operation.client_request_id !== pending.id)
				throw new Error(__("The server result was not confirmed. Retry to check its status."));
			localStorage.removeItem(this.pending_key());
			return result;
		} catch (error) {
			if (error?.exc_type || error?.responseJSON?.exc_type) {
				try {
					const outcome = await this.call("service.get_outcome", { client_request_id: pending.id });
					if (outcome.status === "not_found") localStorage.removeItem(this.pending_key());
				} catch {
					/* Unknown outcome retains the exact original intent. */
				}
			}
			throw error;
		}
	}
	render_recovery() {
		if (!this.wrapper.find(".sr-recovery").length)
			this.wrapper.prepend('<div class="sr-recovery" aria-live="polite"></div>');
		const area = this.wrapper.find(".sr-recovery").empty();
		try {
			const pending = this.pending();
			if (!pending) return;
			area.html(
				`<p>${__("Unconfirmed review request")} · ${this.esc(pending.intent.review_name)} · ${this.esc(__(pending.intent.action))}</p><button class="btn btn-default btn-sm" data-check>${__("Check result")}</button> <button class="btn btn-default btn-sm" data-resend>${__("Retry original request")}</button><p class="sr-outcome" role="status"></p>`,
			);
			area.find("[data-check], [data-resend]").on("click", async (event) => {
				area.find("button").prop("disabled", true);
				try {
					const result = event.currentTarget.hasAttribute("data-resend")
						? await this.execute(pending.intent.action, pending.intent.args, {
								review: pending.intent.review_name,
								version: pending.intent.expected_version,
							})
						: await this.call("service.get_outcome", { client_request_id: pending.id });
					if (result.operation?.client_request_id === pending.id) {
						localStorage.removeItem(this.pending_key());
						await this.show();
					} else
						area.find(".sr-outcome").text(
							__(
								"No confirmed outcome yet. The original request is retained for a safe retry.",
							),
						);
				} catch (error) {
					area.find(".sr-outcome").text(
						error.message || __("Could not confirm the result. The saved request is retained."),
					);
				} finally {
					area.find("button").prop("disabled", false);
				}
			});
		} catch {
			area.text(
				__(
					"Saved review evidence cannot be read. Ask a manager to investigate before posting again.",
				),
			);
		}
	}
	async open_expense(row, detail) {
		await frappe.require("/assets/erpnext/js/expense_entry.js");
		if (!this.ready || this.detail?.review !== detail.review || this.dialog || this.entry) return;
		const adapter = {
			...frappe.expense_entry,
			review_entry: { row, detail },
			ready: true,
			company: detail.company,
			data: { currency: detail.currency, can_record: true, can_correct: true },
			filters: {},
			esc: (value) => this.esc(value),
			can_read: (dt) => (frappe.boot.user.can_read || []).includes(dt),
			receipt_url: (value) =>
				typeof value === "string" && /^\/private\/files\/[^?#\\]+$/.test(value) ? value : null,
			perform_expense: async (args) => {
				const current =
					!this.pending() && this.detail?.review === detail.review ? this.detail : detail;
				const current_row = current.accounts.find((item) => item.row_key === row.row_key);
				if (Number(args.amount) > Math.abs(Number(current_row.remaining_amount)))
					throw new Error(__("Enter a positive amount no greater than the remaining difference."));
				if (
					!(await this.confirm(
						`${__("Record missing expense")} · ${detail.closing_shift} · ${row.account} · ${args.amount} ${detail.currency} · ${__(detail.capabilities.expense_options.categories.find((item) => item.name === args.category)?.category_name || args.category)} · ${args.posting_date} · ${__("Remaining after explanation")}: ${Number(current_row.remaining_amount) + Number(args.amount)} ${current.currency}`,
					))
				)
					return null;
				return this.execute(
					"Missing expense",
					{
						row_key: row.row_key,
						reason: args.correction_reason,
						signed_amount: -Number(args.amount),
						amount: args.amount,
						category: args.category,
						description: args.description,
						beneficiary_name: args.beneficiary_name,
						receipt_attachment: args.receipt_attachment,
						posting_date: args.posting_date,
					},
					current,
				);
			},
			load: () => this.show(),
			render_recovery: () => this.render_recovery(),
		};
		this.entry = adapter;
		try {
			await adapter.open_entry(true);
			const entry = adapter.entry;
			if (!entry) {
				if (this.entry === adapter) this.entry = null;
				return;
			}
			const onhide = entry.onhide;
			entry.onhide = () => {
				onhide();
				if (this.entry === adapter) this.entry = null;
			};
		} catch (error) {
			if (this.entry === adapter) this.entry = null;
			frappe.msgprint(this.esc(error.message));
		}
	}
}
