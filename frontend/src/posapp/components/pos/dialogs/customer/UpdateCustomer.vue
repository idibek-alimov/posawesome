<template>
	<v-row justify="center">
		<v-dialog
			v-model="isUpdateCustomerDialogOpen"
			max-width="620px"
			persistent
			@keydown.esc.capture.stop.prevent="handleDialogEscape"
			@keydown.ctrl.enter.stop.prevent="submit_dialog"
		>
			<v-card class="update-customer-card">
				<v-card-title class="d-flex align-center pb-1">
					<span v-if="customer_id" class="text-h6 font-weight-bold text-primary">
						{{ __("Update Customer") }}
					</span>
					<span v-else class="text-h6 font-weight-bold text-primary">
						{{ __("Create Customer") }}
					</span>
					<v-spacer></v-spacer>
					<v-btn
						icon="mdi-close"
						variant="text"
						density="compact"
						:aria-label="__('Close')"
						@click="confirm_close"
					></v-btn>
				</v-card-title>
				<v-card-text class="pt-2 pb-2">
					<v-container class="pa-0">
						<!-- Inline live duplicate alert (replaces blocking window.confirm) -->
						<v-alert
							v-if="liveDuplicateCustomer"
							type="warning"
							variant="tonal"
							density="compact"
							class="mb-3 duplicate-customer-banner"
						>
							<div class="d-flex align-center justify-space-between flex-wrap ga-2">
								<div>
									<div class="text-subtitle-2 font-weight-bold">
										{{ __("Customer already exists") }}:
										{{ liveDuplicateCustomer.customer_name || liveDuplicateCustomer.name }}
									</div>
									<div class="text-caption">
										<span v-if="liveDuplicateCustomer.mobile_no">
											{{ __("Mobile No") }}: {{ liveDuplicateCustomer.mobile_no }}
										</span>
										<span v-if="liveDuplicateCustomer.posa_barcode" class="ml-2">
											• {{ __("Card Barcode") }}: {{ liveDuplicateCustomer.posa_barcode }}
										</span>
										<span v-if="liveDuplicateCustomer.customer_group" class="ml-2">
											• {{ liveDuplicateCustomer.customer_group }}
										</span>
									</div>
								</div>
								<v-btn
									color="primary"
									size="small"
									variant="elevated"
									@click="selectExistingDuplicate(liveDuplicateCustomer)"
								>
									{{ __("Select Customer") }}
								</v-btn>
							</div>
						</v-alert>

						<v-row dense>
							<!-- Row 1: Mobile No & Customer Name -->
							<v-col cols="12" sm="6">
								<v-text-field
									ref="mobileNoField"
									density="compact"
									color="primary"
									:label="frappe._('Mobile No') + ' *'"
									class="pos-themed-input"
									hide-details
									v-model="mobile_no"
									placeholder="+992 98 610 4141"
									prepend-inner-icon="mdi-phone-outline"
									@update:model-value="scheduleLiveDuplicateCheck"
									@keydown.enter.prevent="handleMobileEnter"
								></v-text-field>
							</v-col>
							<v-col cols="12" sm="6">
								<v-text-field
									ref="customerNameField"
									density="compact"
									color="primary"
									:label="frappe._('Customer Name') + ' *'"
									hide-details
									class="pos-themed-input"
									v-model="customer_name"
									placeholder="Имя Фамилия"
									prepend-inner-icon="mdi-account-outline"
									@keydown.enter.prevent="handleNameEnter"
								></v-text-field>
							</v-col>

							<!-- Row 2: Customer Barcode (Card) & Date of Birth -->
							<v-col cols="12" sm="6" class="mt-2">
								<v-text-field
									ref="barcodeField"
									density="compact"
									color="primary"
									:label="__('Card Barcode')"
									class="pos-themed-input"
									hide-details
									clearable
									v-model="posa_barcode"
									:placeholder="__('Scan or generate card')"
									prepend-inner-icon="mdi-barcode-scan"
									@update:model-value="scheduleLiveDuplicateCheck"
									@keydown.enter.prevent="handleBarcodeEnter"
								>
									<template #append-inner>
										<v-tooltip
											:text="__('Generate Card Barcode')"
											content-class="posa-theme-tooltip"
										>
											<template #activator="{ props }">
												<v-icon
													v-bind="props"
													size="small"
													class="cursor-pointer"
													role="button"
													tabindex="0"
													:aria-label="__('Generate Card Barcode')"
													@mousedown.prevent.stop
													@click.stop="generateCardBarcode"
												>
													mdi-auto-fix
												</v-icon>
											</template>
										</v-tooltip>
									</template>
								</v-text-field>
							</v-col>
							<v-col cols="12" sm="6" class="mt-2">
								<v-text-field
									ref="birthdayField"
									v-model="birthday"
									:label="frappe._('Date of Birth (DD.MM.YYYY)')"
									density="compact"
									clearable
									hide-details
									color="primary"
									placeholder="ДД.ММ.ГГГГ"
									prepend-inner-icon="mdi-cake-variant-outline"
									@update:model-value="formatBirthdayOnInput"
									@keydown.enter.prevent="handleBirthdayEnter"
									class="pos-themed-input"
								></v-text-field>
							</v-col>

							<!-- Row 3: Customer Tier (1-tap pills when configured, autocomplete fallback) -->
							<v-col cols="12" class="mt-3">
								<div class="text-caption font-weight-medium mb-1 text-medium-emphasis">
									{{ frappe._("Customer Tier") }} *
								</div>
								<div v-if="tierOptions && tierOptions.length > 0" class="tier-pill-group">
									<v-btn
										v-for="tierItem in tierOptions"
										:key="tierItem.name"
										size="small"
										:variant="group === tierItem.name ? 'elevated' : 'outlined'"
										:color="group === tierItem.name ? 'primary' : undefined"
										class="tier-pill-btn text-none"
										@click="group = tierItem.name"
									>
										<v-icon
											size="16"
											class="mr-1"
											:icon="
												group === tierItem.name
													? 'mdi-check-circle'
													: 'mdi-star-circle-outline'
											"
										></v-icon>
										<span class="font-weight-bold">{{ tierItem.name }}</span>
										<span class="text-caption ml-1 opacity-80">
											({{ tierItem.shortMeta }})
										</span>
									</v-btn>
								</div>
								<v-autocomplete
									v-else
									clearable
									density="compact"
									auto-select-first
									color="primary"
									:label="frappe._('Customer Tier') + ' *'"
									v-model="group"
									:items="tierSelectItems"
									item-title="label"
									item-value="name"
									class="pos-themed-input"
									:no-data-text="__('Tier not found')"
									hide-details
									required
								>
								</v-autocomplete>
							</v-col>

							<!-- Existing loyalty info if editing an active loyalty customer -->
							<v-col cols="6" v-if="loyalty_program" class="mt-2">
								<v-text-field
									v-model="loyalty_program"
									:label="frappe._('Loyalty Program')"
									density="compact"
									readonly
									hide-details
									class="pos-themed-input"
								></v-text-field>
							</v-col>
							<v-col cols="6" v-if="loyalty_points !== null && loyalty_points !== undefined" class="mt-2">
								<v-text-field
									v-model="loyalty_points"
									:label="frappe._('Loyalty Points')"
									density="compact"
									readonly
									hide-details
									class="pos-themed-input"
								></v-text-field>
							</v-col>

							<!-- Progressive disclosure toggle for occasional details -->
							<v-col cols="12" class="mt-2">
								<v-btn
									variant="text"
									size="small"
									color="primary"
									class="px-1 text-none"
									:prepend-icon="hideNonEssential ? 'mdi-chevron-right' : 'mdi-chevron-down'"
									@click="hideNonEssential = !hideNonEssential"
								>
									{{
										hideNonEssential
											? __("Additional Details (Tax ID, Address, Email)")
											: __("Hide Additional Details")
									}}
								</v-btn>
							</v-col>

							<!-- Non-essential details (disclosed when hideNonEssential is false) -->
							<v-col cols="6" v-if="!hideNonEssential">
								<v-text-field
									density="compact"
									color="primary"
									:label="frappe._('Tax ID')"
									class="pos-themed-input"
									hide-details
									v-model="tax_id"
								></v-text-field>
							</v-col>
							<v-col cols="6" v-if="!hideNonEssential">
								<v-text-field
									density="compact"
									color="primary"
									:label="frappe._('Email Id')"
									class="pos-themed-input"
									hide-details
									v-model="email_id"
								></v-text-field>
							</v-col>
							<v-col cols="12" v-if="!hideNonEssential" class="mt-2">
								<v-text-field
									density="compact"
									color="primary"
									:label="__('Address Line 1')"
									hide-details
									class="pos-themed-input"
									v-model="address_line1"
								></v-text-field>
							</v-col>

							<v-col cols="12" sm="6" v-if="!hideNonEssential" class="mt-2">
								<v-text-field
									v-model="city"
									variant="outlined"
									density="compact"
									hide-details
									:label="__('City')"
									class="pos-themed-input"
								></v-text-field>
							</v-col>

							<v-col cols="12" sm="6" v-if="!hideNonEssential" class="mt-2">
								<v-select
									v-model="country"
									:items="countries"
									variant="outlined"
									density="compact"
									hide-details
									:label="__('Country')"
									class="pos-themed-input"
								></v-select>
							</v-col>

							<v-col cols="6" v-if="!hideNonEssential" class="mt-2">
								<v-select
									density="compact"
									hide-details
									:label="__('Gender')"
									:items="genders"
									v-model="gender"
									class="pos-themed-input"
								></v-select>
							</v-col>
							<v-col cols="6" v-if="!hideNonEssential" class="mt-2">
								<v-text-field
									density="compact"
									color="primary"
									:label="frappe._('Referral Code')"
									class="pos-themed-input"
									hide-details
									v-model="referral_code"
								></v-text-field>
							</v-col>
							<v-col cols="12" v-if="!hideNonEssential" class="mt-2">
								<v-autocomplete
									clearable
									density="compact"
									auto-select-first
									color="primary"
									:label="frappe._('Territory') + ' *'"
									v-model="territory"
									:items="territorys"
									class="pos-themed-input"
									:no-data-text="__('Territory not found')"
									hide-details
									required
								>
								</v-autocomplete>
							</v-col>
						</v-row>
					</v-container>
				</v-card-text>
				<v-card-actions class="px-4 pb-3 pt-1">
					<span class="text-caption text-medium-emphasis d-none d-sm-inline">
						Ctrl + Enter — {{ __("Submit") }}
					</span>
					<v-spacer></v-spacer>
					<v-btn variant="text" color="error" @click="confirm_close">
						{{ __("Close") }}
					</v-btn>
					<v-btn
						color="success"
						variant="elevated"
						:loading="isSubmitting"
						:disabled="isSubmitting"
						@click="submit_dialog"
					>
						{{ customer_id ? __("Save") : __("Submit") }}
					</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>

		<!-- Confirmation Dialog -->
		<v-dialog
			v-model="confirmDialog"
			max-width="400px"
			@keydown.esc.capture.stop.prevent="handleConfirmEscape"
		>
			<v-card>
				<v-card-title class="text-h5 text-primary">
					{{ __("Confirm Close") }}
				</v-card-title>
				<v-card-text>
					{{ __("Are you sure you want to close? All entered data will be lost.") }}
				</v-card-text>
				<v-card-actions>
					<v-spacer></v-spacer>
					<v-btn color="primary" @click="confirmDialog = false">
						{{ __("Continue Editing") }}
					</v-btn>
					<v-btn color="error" @click="confirmClose">
						{{ __("Yes, Close") }}
					</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</v-row>
</template>

<script>
import { isOffline, saveOfflineCustomer } from "../../../../../offline/index";
import { useCustomersStore } from "../../../../stores/customersStore.js";
import {
	formatCustomerBirthdayDisplay,
	generateCustomerCardBarcode,
} from "../../../../stores/customers/customerSearch";
import { useUIStore } from "../../../../stores/uiStore.js";
import { storeToRefs } from "pinia";
import { useToastStore } from "../../../../stores/toastStore.js";

export default {
	setup() {
		const customersStore = useCustomersStore();
		const uiStore = useUIStore();
		const toastStore = useToastStore();
		const {
			selectedCustomer,
			isUpdateCustomerDialogOpen,
			customerToUpdate,
			pendingCustomerPrefill,
		} = storeToRefs(customersStore);
		return {
			selectedCustomer,
			uiStore,
			toastStore,
			isUpdateCustomerDialogOpen,
			customerToUpdate,
			pendingCustomerPrefill,
			customersStore,
		};
	},
	data: () => ({
		confirmDialog: false,
		isSubmitting: false,
		liveDuplicateCustomer: null,
		duplicateCheckTimer: null,
		pos_profile: "",
		customer_id: "",
		customer_name: "",
		tax_id: "",
		mobile_no: "",
		posa_barcode: "",
		address_line1: "",
		city: "",
		country: "Tajikistan",
		email_id: "",
		referral_code: "",
		birthday: "",
		birthday_menu: false,
		group: "",
		groups: [],
		tierOptions: [],
		defaultTier: "Базовый",
		territory: "",
		territorys: [],
		genders: [],
		customer_type: "Individual",
		gender: "",
		loyalty_points: null,
		loyalty_program: null,
		hideNonEssential: true,
		countries: [
			"Tajikistan",
			"Afghanistan",
			"Australia",
			"Bahrain",
			"Bangladesh",
			"Canada",
			"China",
			"Denmark",
			"France",
			"Germany",
			"India",
			"Indonesia",
			"Italy",
			"Japan",
			"Kuwait",
			"Malaysia",
			"Nepal",
			"Netherlands",
			"New Zealand",
			"Norway",
			"Oman",
			"Pakistan",
			"Philippines",
			"Qatar",
			"Russia",
			"Saudi Arabia",
			"Singapore",
			"South Korea",
			"Spain",
			"Sri Lanka",
			"Sweden",
			"Switzerland",
			"Syria",
			"Thailand",
			"Turkey",
			"United Arab Emirates",
			"United Kingdom",
			"United States",
			"Uzbekistan",
			"Vietnam",
			"Yemen",
		],
	}),
	watch: {
		hideNonEssential(val) {
			if (typeof localStorage !== "undefined") {
				localStorage.setItem("posawesome_hide_non_essential_fields", JSON.stringify(val));
			}
		},
		birthday(newVal) {
			// Check if the user has entered 8 digits without separators (e.g., 04111994)
			if (newVal && /^\d{8}$/.test(newVal)) {
				try {
					const day = newVal.substring(0, 2);
					const month = newVal.substring(2, 4);
					const year = newVal.substring(4);

					// Format it as a hyphenated date for display
					this.birthday = `${day}-${month}-${year}`;

					// Update calendar (implemented below)
					this.updateCalendarDate(day, month, year);
				} catch (error) {
					console.error("Error processing 8-digit date:", error);
				}
			}
			// Check if the date is already in DD-MM-YYYY format
			else if (newVal && /^\d{2}-\d{2}-\d{4}$/.test(newVal)) {
				try {
					const parts = newVal.split("-");
					const day = parts[0];
					const month = parts[1];
					const year = parts[2];

					// Update calendar to show the correct month
					this.updateCalendarDate(day, month, year);
				} catch (error) {
					console.error("Error processing formatted date:", error);
				}
			}
		},

		// Add a watcher for the calendar menu to ensure it shows the right date when opened
		birthday_menu(isOpen) {
			if (isOpen && this.birthday && /^\d{2}-\d{2}-\d{4}$/.test(this.birthday)) {
				try {
					const parts = this.birthday.split("-");
					const day = parts[0];
					const month = parts[1];
					const year = parts[2];

					// Update calendar date when menu opens
					this.$nextTick(() => {
						this.updateCalendarDate(day, month, year);
					});
				} catch (error) {
					console.error("Error updating calendar on menu open:", error);
				}
			}
		},
	},
	computed: {
		tierSelectItems() {
			if (this.tierOptions && this.tierOptions.length > 0) {
				return this.tierOptions;
			}
			return this.groups.map((g) => ({ name: g, label: g }));
		},
	},
	methods: {
		focusField(refName) {
			this.$nextTick(() => {
				const field = this.$refs[refName];
				if (field && typeof field.focus === "function") {
					field.focus();
				}
			});
		},
		focusCustomerNameField() {
			this.focusField("customerNameField");
		},
		focusFirstField() {
			this.$nextTick(() => {
				let targetRef = "mobileNoField";
				if (this.customer_id) {
					targetRef = "customerNameField";
				} else if (this.mobile_no && !this.customer_name) {
					targetRef = "customerNameField";
				} else if (this.mobile_no && this.customer_name && !this.posa_barcode) {
					targetRef = "barcodeField";
				}
				const field = this.$refs[targetRef] || this.$refs.customerNameField;
				if (field && typeof field.focus === "function") {
					field.focus();
				}
			});
		},
		handleMobileEnter() {
			if (!this.customer_name) {
				this.focusField("customerNameField");
			} else if (!this.posa_barcode) {
				this.focusField("barcodeField");
			} else {
				this.submit_dialog();
			}
		},
		handleNameEnter() {
			if (!this.mobile_no && !this.customer_id) {
				this.focusField("mobileNoField");
			} else if (!this.posa_barcode) {
				this.focusField("barcodeField");
			} else if (!this.birthday) {
				this.focusField("birthdayField");
			} else {
				this.submit_dialog();
			}
		},
		handleBarcodeEnter() {
			if (!this.mobile_no && !this.customer_id) {
				this.focusField("mobileNoField");
			} else if (!this.customer_name) {
				this.focusField("customerNameField");
			} else if (!this.birthday) {
				this.focusField("birthdayField");
			} else {
				this.submit_dialog();
			}
		},
		handleBirthdayEnter() {
			if (!this.mobile_no && !this.customer_id) {
				this.focusField("mobileNoField");
			} else if (!this.customer_name) {
				this.focusField("customerNameField");
			} else {
				this.submit_dialog();
			}
		},
		generateCardBarcode() {
			this.posa_barcode = generateCustomerCardBarcode();
			this.scheduleLiveDuplicateCheck();
		},
		scheduleLiveDuplicateCheck() {
			if (this.duplicateCheckTimer) {
				clearTimeout(this.duplicateCheckTimer);
			}
			this.duplicateCheckTimer = setTimeout(() => {
				void this.checkLiveDuplicate();
			}, 180);
		},
		async checkLiveDuplicate() {
			const cleanMobile = String(this.mobile_no || "").replace(/\D/g, "");
			const cleanBarcode = String(this.posa_barcode || "").trim();
			if (cleanMobile.length < 7 && cleanBarcode.length < 3) {
				this.liveDuplicateCustomer = null;
				return;
			}
			try {
				const matches = await this.customersStore.findLocalDuplicateCustomers(
					{
						mobile_no: cleanMobile.length >= 7 ? this.mobile_no : "",
						posa_barcode: cleanBarcode.length >= 3 ? cleanBarcode : "",
					},
					this.customer_id || null,
				);
				this.liveDuplicateCustomer = matches.length > 0 ? matches[0] : null;
			} catch (err) {
				console.error("Live duplicate check error:", err);
			}
		},
		async selectExistingDuplicate(existing) {
			if (!existing || !existing.name) return;
			await this.customersStore.addOrUpdateCustomer(existing);
			this.customersStore.setSelectedCustomer(existing.name);
			this.toastStore.show({
				title: __("Existing customer selected"),
				color: "info",
			});
			this.close_dialog();
		},
		handleDialogEscape() {
			if (this.confirmDialog) {
				this.confirmClose();
				return;
			}
			this.confirm_close();
		},
		handleConfirmEscape() {
			this.confirmClose();
		},
		// Add a new method to update calendar date
		updateCalendarDate(day, month, year) {
			// First close the date picker if it's open
			const wasOpen = this.birthday_menu;
			this.birthday_menu = false;

			// Use nextTick to ensure DOM updates
			this.$nextTick(() => {
				// Format date in YYYY-MM-DD format for Vuetify
				const tempDate = `${year}-${month}-${day}`;

				// Try to directly set the calendar's date
				setTimeout(() => {
					if (this.$refs.birthday_menu) {
						this.$refs.birthday_menu.date = tempDate;
						// Optionally reopen menu if it was open
						if (wasOpen) {
							this.birthday_menu = true;
						}
					}
				}, 50);
			});
		},
		confirm_close() {
			// Check if any data has been entered
			if (
				this.customer_name ||
				this.tax_id ||
				this.mobile_no ||
				this.posa_barcode ||
				this.address_line1 ||
				this.email_id ||
				this.referral_code ||
				this.birthday
			) {
				this.confirmDialog = true;
			} else {
				// If no data entered, just close
				this.close_dialog();
			}
		},
		confirmClose() {
			this.confirmDialog = false;
			this.close_dialog();
		},
		close_dialog() {
			this.customersStore.closeUpdateCustomerDialog();
			this.clear_customer();
		},
		clear_customer() {
			if (this.duplicateCheckTimer) {
				clearTimeout(this.duplicateCheckTimer);
				this.duplicateCheckTimer = null;
			}
			this.liveDuplicateCustomer = null;
			this.isSubmitting = false;
			this.customer_name = "";
			this.tax_id = "";
			this.mobile_no = "";
			this.posa_barcode = "";
			this.address_line1 = "";
			this.city = "";
			this.country = (this.pos_profile && this.pos_profile.posa_default_country) || "Tajikistan";
			this.email_id = "";
			this.referral_code = "";
			this.birthday = "";
			this.group = this.defaultTier || frappe.defaults.get_user_default("Customer Group") || "Базовый";
			this.territory = frappe.defaults.get_user_default("Territory") || "All Territories";
			this.customer_id = "";
			this.customer_type = "Individual";
			this.gender = "";
			this.loyalty_points = null;
			this.loyalty_program = null;
		},
		getCustomerTiers() {
			const vm = this;
			frappe.call({
				method: "posawesome.posawesome.api.customers.get_customer_tiers",
				callback: (r) => {
					if (r && r.message && r.message.tiers && r.message.tiers.length > 0) {
						vm.defaultTier = r.message.default_tier || "Базовый";
						vm.tierOptions = r.message.tiers.map((t) => {
							const disc = Number(t.discount_percentage || 0);
							const pts = Number(t.points_percentage || 0);
							const shortMeta = `${disc}% / +${pts}%`;
							const label = `${t.name} (${disc}% ${frappe._("discount") || "скидка"} / ${pts}% ${frappe._("points") || "баллы"})`;
							return {
								name: t.name,
								label: label,
								shortMeta: shortMeta,
								discount: disc,
								points: pts,
							};
						});
						if (!vm.customer_id && !vm.group) {
							vm.group = vm.defaultTier;
						}
					}
				},
			});
		},
		getCustomerGroups() {
			if (this.groups.length > 0) return;
			const vm = this;
			frappe.db
				.get_list("Customer Group", {
					fields: ["name"],
					filters: { is_group: 0 },
					limit: 1000,
					order_by: "name",
				})
				.then((data) => {
					if (data.length > 0) {
						data.forEach((el) => {
							vm.groups.push(el.name);
						});
					}
				});
		},
		getCustomerTerritorys() {
			if (this.territorys.length > 0) return;
			const vm = this;
			frappe.db
				.get_list("Territory", {
					fields: ["name"],
					filters: { is_group: 0 },
					limit: 5000,
					order_by: "name",
				})
				.then((data) => {
					if (data.length > 0) {
						data.forEach((el) => {
							vm.territorys.push(el.name);
						});
					}
				});
		},
		getGenders() {
			const vm = this;
			frappe.db
				.get_list("Gender", {
					fields: ["name"],
					page_length: 10,
				})
				.then((data) => {
					if (data.length > 0) {
						data.forEach((el) => {
							vm.genders.push(el.name);
						});
					}
				});
		},
		formatBirthdayOnInput(val) {
			const raw = String(val !== undefined ? val : this.birthday || "");
			const digits = raw.replace(/\D/g, "").slice(0, 8);
			if (/^\d{8}$/.test(digits)) {
				const day = digits.substring(0, 2);
				const month = digits.substring(2, 4);
				const year = digits.substring(4, 8);
				this.birthday = `${day}.${month}.${year}`;
			}
		},
		parseAndValidateBirthday(input) {
			const raw = String(input || "").trim();
			if (!raw) return { valid: true, formatted: null };
			let day = 0;
			let month = 0;
			let year = 0;
			if (/^\d{8}$/.test(raw)) {
				day = Number(raw.slice(0, 2));
				month = Number(raw.slice(2, 4));
				year = Number(raw.slice(4, 8));
			} else if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(raw)) {
				const parts = raw.split("-");
				year = Number(parts[0]);
				month = Number(parts[1]);
				day = Number(parts[2]);
			} else if (/^\d{1,2}[-./]\d{1,2}[-./]\d{4}$/.test(raw)) {
				const parts = raw.split(/[-./]/);
				day = Number(parts[0]);
				month = Number(parts[1]);
				year = Number(parts[2]);
			} else {
				return { valid: false, formatted: null };
			}
			const currentYear = new Date().getFullYear();
			if (year < 1920 || year > currentYear || month < 1 || month > 12 || day < 1 || day > 31) {
				return { valid: false, formatted: null };
			}
			const checkDate = new Date(year, month - 1, day);
			if (
				checkDate.getFullYear() !== year ||
				checkDate.getMonth() !== month - 1 ||
				checkDate.getDate() !== day
			) {
				return { valid: false, formatted: null };
			}
			return {
				valid: true,
				formatted: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
			};
		},
		async submit_dialog() {
			if (this.isSubmitting) return;
			const vm = this;
			this.customer_name = (this.customer_name || "").trim();
			this.mobile_no = (this.mobile_no || "").trim();
			this.posa_barcode = (this.posa_barcode || "").trim();

			if (!this.customer_name) {
				frappe.throw(__("Customer Name is required"));
				return;
			}

			if (!this.customer_id && !this.mobile_no) {
				frappe.throw(__("Mobile number is required for customer registration"));
				return;
			}

			if (!this.group) {
				this.group = this.defaultTier || "Базовый";
			}

			if (!this.territory) {
				this.territory = frappe.defaults.get_user_default("Territory") || "All Territories";
			}

			const bdayResult = this.parseAndValidateBirthday(this.birthday);
			if (!bdayResult.valid) {
				vm.toastStore.show({
					title: __("Invalid Date of Birth. Use DD.MM.YYYY format."),
					color: "error",
				});
				return;
			}
			const formatted_birthday = bdayResult.formatted;

			// Create args object to use in callback
			const args = {
				customer_id: this.customer_id,
				customer_name: this.customer_name,
				tax_id: this.tax_id,
				mobile_no: this.mobile_no,
				posa_barcode: this.posa_barcode || null,
				address_line1: this.address_line1,
				city: this.city,
				country: this.country,
				email_id: this.email_id,
				referral_code: this.referral_code,
				birthday: formatted_birthday || null,
				posa_birthday: formatted_birthday || null,
				customer_group: this.group,
				tier: this.group,
				territory: this.territory,
				customer_type: this.customer_type,
				gender: this.gender,
			};
			const apiArgs = {
				...args,
				company: vm.pos_profile.company,
				pos_profile_doc: JSON.stringify(vm.pos_profile),
				method: this.customer_id ? "update" : "create",
			};

			const customersStore = useCustomersStore();
			this.isSubmitting = true;
			try {
				let duplicateCustomers = await customersStore.findLocalDuplicateCustomers(
					args,
					this.customer_id || null,
				);
				if (!isOffline() && !duplicateCustomers.length) {
					const duplicateResponse = await frappe.call({
						method: "posawesome.posawesome.api.customers.find_duplicate_customers",
						args: {
							customer_name: args.customer_name,
							mobile_no: args.mobile_no,
							email_id: args.email_id,
							tax_id: args.tax_id,
							posa_barcode: args.posa_barcode,
							customer_id: this.customer_id || null,
							company: vm.pos_profile.company,
							pos_profile_doc: JSON.stringify(vm.pos_profile),
						},
					});
					duplicateCustomers = duplicateResponse.message || [];
				}

				if (duplicateCustomers.length) {
					const existing = duplicateCustomers[0];
					this.liveDuplicateCustomer = existing;
					this.isSubmitting = false;
					vm.toastStore.show({
						title: __("Customer with this phone or card already exists"),
						color: "warning",
					});
					return;
				}
			} catch (err) {
				this.isSubmitting = false;
				console.error("Duplicate customer check failed:", err);
			}

			if (isOffline()) {
				await saveOfflineCustomer({ args: apiArgs });
				vm.toastStore.show({ title: __("Customer saved offline"), color: "warning" });
				args.name = this.customer_id || this.customer_name;
				await customersStore.addOrUpdateCustomer({
					name: args.name,
					customer_name: args.customer_name,
					customer_group: args.customer_group,
					mobile_no: args.mobile_no,
					posa_barcode: args.posa_barcode,
					posa_birthday: args.posa_birthday,
					birthday: args.posa_birthday,
					email_id: args.email_id,
					tax_id: args.tax_id,
					primary_address: args.address_line1,
				});
				customersStore.setSelectedCustomer(args.name);
				vm.close_dialog();
				return;
			}

			frappe.call({
				method: "posawesome.posawesome.api.customers.create_customer",
				args: apiArgs,
				callback: async (r) => {
					vm.isSubmitting = false;
					if (!r.exc && r.message && r.message.name) {
						let text = __("Customer created successfully.");
						if (vm.customer_id) {
							text = __("Customer updated successfully.");
						}
						vm.toastStore.show({
							title: text,
							color: "success",
						});
						frappe.utils.play_sound("submit");
						const saved = {
							...r.message,
							name: r.message.name,
							customer_name: r.message.customer_name || args.customer_name,
							customer_group: r.message.customer_group || args.customer_group,
							loyalty_program: r.message.loyalty_program || args.loyalty_program,
							mobile_no: r.message.mobile_no || args.mobile_no,
							posa_barcode: r.message.posa_barcode ?? args.posa_barcode,
							posa_birthday: r.message.posa_birthday || args.posa_birthday,
							birthday: r.message.posa_birthday || args.posa_birthday,
							email_id: r.message.email_id || args.email_id,
							tax_id: r.message.tax_id || args.tax_id,
							primary_address: args.address_line1,
						};
						await customersStore.addOrUpdateCustomer(saved);
						customersStore.setSelectedCustomer(saved.name);
						vm.close_dialog();
					} else {
						frappe.utils.play_sound("error");
						vm.toastStore.show({
							title: __("Customer creation failed."),
							color: "error",
						});
					}
				},
				error: () => {
					vm.isSubmitting = false;
				},
			});
		},
		onDateSelect() {
			// Close the menu
			this.birthday_menu = false;

			// Format date if it's a JavaScript Date object or full date string (from date picker)
			if (this.birthday) {
				try {
					// Handle both JavaScript Date objects and strings with GMT
					let dateObj;
					if (typeof this.birthday === "object") {
						dateObj = this.birthday;
					} else if (
						typeof this.birthday === "string" &&
						(this.birthday.includes("GMT") || this.birthday.includes("T"))
					) {
						dateObj = new Date(this.birthday);
					} else {
						// Already formatted or something else, leave it
						return;
					}

					const year = dateObj.getFullYear();
					const month = String(dateObj.getMonth() + 1).padStart(2, "0");
					const day = String(dateObj.getDate()).padStart(2, "0");

					// Format as DD-MM-YYYY
					this.birthday = `${day}-${month}-${year}`;
				} catch (error) {
					console.error("Error formatting date from picker:", error);
				}
			}
		},
	},
	created: function () {
		if (typeof localStorage !== "undefined") {
			const saved = localStorage.getItem("posawesome_hide_non_essential_fields");
			if (saved !== null) {
				this.hideNonEssential = JSON.parse(saved);
			}
		}
		// Watch store state for dialog opening
		this.$watch(
			() => this.isUpdateCustomerDialogOpen,
			(isOpen) => {
				if (isOpen) {
					this.focusFirstField();
					const data = this.customerToUpdate;
					if (data) {
						this.customer_name = data.customer_name || data.name || ""; // fallback
						this.customer_id = data.name;
						this.address_line1 = data.primary_address || data.address_line1 || "";
						this.city = data.city || "";
						this.country =
							data.country ||
							(this.pos_profile && this.pos_profile.posa_default_country) ||
							"Tajikistan";
						this.tax_id = data.tax_id;
						this.mobile_no = data.mobile_no;
						this.posa_barcode = data.posa_barcode || "";
						this.email_id = data.email_id;
						this.referral_code = data.referral_code;
						this.birthday = formatCustomerBirthdayDisplay(
							data.posa_birthday || data.birthday,
						);
						this.group = data.customer_group || this.defaultTier || "Базовый";
						this.territory = data.territory;
						this.loyalty_points = data.loyalty_points;
						this.loyalty_program = data.loyalty_program;
						this.gender = data.gender;
					} else {
						// Setup for new customer
						this.clear_customer();
						const prefill = this.pendingCustomerPrefill;
						if (prefill) {
							if (prefill.mobile_no) this.mobile_no = prefill.mobile_no;
							if (prefill.customer_name) this.customer_name = prefill.customer_name;
							if (prefill.posa_barcode) this.posa_barcode = prefill.posa_barcode;
							this.scheduleLiveDuplicateCheck();
						}
					}
					this.focusFirstField();
				}
			},
		);

		// Watch Store for POS Profile
		this.$watch(
			() => this.uiStore.posProfile,
			(profile) => {
				if (profile) {
					this.pos_profile = profile;
					this.country = (profile && profile.posa_default_country) || "Tajikistan";
				}
			},
			{ deep: true, immediate: true },
		);

		this.getCustomerTiers();
		this.getCustomerGroups();
		this.getCustomerTerritorys();
		this.getGenders();
		// set default values for customer group and territory from user defaults
		this.group = frappe.defaults.get_user_default("Customer Group");
		this.territory = frappe.defaults.get_user_default("Territory");
	},
};
</script>

<style scoped>
.tier-pill-group {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
}

.tier-pill-btn {
	flex: 1 1 auto;
	min-height: 36px;
	border-radius: 8px;
}

.duplicate-customer-banner {
	border-radius: 10px;
}
</style>
