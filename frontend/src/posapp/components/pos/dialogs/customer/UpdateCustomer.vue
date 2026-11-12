<template>
	<v-row justify="center">
		<v-dialog
			v-model="isUpdateCustomerDialogOpen"
			max-width="600px"
			persistent
			@keydown.esc.capture.stop.prevent="handleDialogEscape"
		>
			<v-card>
				<v-card-title class="d-flex align-center">
					<span v-if="customer_id" class="text-h5 text-primary">{{ __("Update Customer") }}</span>
					<span v-else class="text-h5 text-primary">{{ __("Create Customer") }}</span>
					<v-spacer></v-spacer>
					<v-switch
						v-model="hideNonEssential"
						density="compact"
						inset
						hide-details
						color="primary"
						:label="__('Hide Non Essential Fields')"
					></v-switch>
				</v-card-title>
				<v-card-text class="pa-0">
					<v-container>
						<v-row>
							<!-- Core Quick Registration fields: Mobile No, Customer Name, Tier -->
							<v-col cols="12" sm="6">
								<v-text-field
									ref="mobileNoField"
									density="compact"
									color="primary"
									:label="frappe._('Mobile No') + ' *'"
									class="pos-themed-input"
									hide-details
									v-model="mobile_no"
									placeholder="+992 986104141"
									@keydown.enter="handleEnterKey"
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
									@keydown.enter="handleEnterKey"
								></v-text-field>
							</v-col>
							<v-col cols="12">
								<v-autocomplete
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
							<v-col cols="12" v-if="!hideNonEssential">
								<v-text-field
									density="compact"
									color="primary"
									:label="__('Address Line 1')"
									hide-details
									class="pos-themed-input"
									v-model="address_line1"
								></v-text-field>
							</v-col>

							<v-col cols="12" sm="6" v-if="!hideNonEssential">
								<v-text-field
									v-model="city"
									variant="outlined"
									density="compact"
									:label="__('City')"
									class="pos-themed-input"
								></v-text-field>
							</v-col>

							<v-col cols="12" sm="6" v-if="!hideNonEssential">
								<v-select
									v-model="country"
									:items="countries"
									variant="outlined"
									density="compact"
									:label="__('Country')"
									class="pos-themed-input"
								></v-select>
							</v-col>

							<v-col cols="6" v-if="!hideNonEssential">
								<v-select
									density="compact"
									:label="__('Gender')"
									:items="genders"
									v-model="gender"
									class="pos-themed-input"
								></v-select>
							</v-col>
							<v-col cols="6" v-if="!hideNonEssential">
								<v-text-field
									density="compact"
									color="primary"
									:label="frappe._('Referral Code')"
									class="pos-themed-input"
									hide-details
									v-model="referral_code"
								></v-text-field>
							</v-col>
							<v-col cols="6" v-if="!hideNonEssential">
								<v-text-field
									v-model="birthday"
									:label="frappe._('Birthday (DD-MM-YYYY)')"
									density="compact"
									clearable
									hide-details
									color="primary"
									placeholder="DD-MM-YYYY"
									@update:model-value="formatBirthdayOnInput"
									class="pos-themed-input"
								></v-text-field>
							</v-col>
							<v-col cols="6" v-if="!hideNonEssential">
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

							<!-- Existing loyalty info if editing an active loyalty customer -->
							<v-col cols="6" v-if="loyalty_program">
								<v-text-field
									v-model="loyalty_program"
									:label="frappe._('Loyalty Program')"
									density="compact"
									readonly
									hide-details
									class="pos-themed-input"
								></v-text-field>
							</v-col>
							<v-col cols="6" v-if="loyalty_points">
								<v-text-field
									v-model="loyalty_points"
									:label="frappe._('Loyalty Points')"
									density="compact"
									readonly
									hide-details
									class="pos-themed-input"
								></v-text-field>
							</v-col>
						</v-row>
					</v-container>
				</v-card-text>
				<v-card-actions>
					<v-spacer></v-spacer>
					<v-btn color="error" theme="dark" @click="confirm_close">{{ __("Close") }}</v-btn>
					<v-btn color="success" theme="dark" @click="submit_dialog">{{ __("Submit") }}</v-btn>
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
import { useUIStore } from "../../../../stores/uiStore.js";
import { storeToRefs } from "pinia";
import { useToastStore } from "../../../../stores/toastStore.js";

export default {
	setup() {
		const customersStore = useCustomersStore();
		const uiStore = useUIStore();
		const toastStore = useToastStore();
		const { selectedCustomer, isUpdateCustomerDialogOpen, customerToUpdate } =
			storeToRefs(customersStore);
		return {
			selectedCustomer,
			uiStore,
			toastStore,
			isUpdateCustomerDialogOpen,
			customerToUpdate,
			customersStore,
		};
	},
	data: () => ({
		// customerDialog: false, // Moved to store
		confirmDialog: false,
		pos_profile: "",
		customer_id: "",
		customer_name: "",
		tax_id: "",
		mobile_no: "",
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
		focusCustomerNameField() {
			this.$nextTick(() => {
				const field = this.$refs.customerNameField;
				if (field && typeof field.focus === "function") {
					field.focus();
				}
			});
		},
		focusFirstField() {
			this.$nextTick(() => {
				const field = this.customer_id
					? this.$refs.customerNameField
					: (this.$refs.mobileNoField || this.$refs.customerNameField);
				if (field && typeof field.focus === "function") {
					field.focus();
				}
			});
		},
		handleEnterKey() {
			if (this.mobile_no && this.customer_name) {
				this.submit_dialog();
			} else if (this.mobile_no && !this.customer_name) {
				const field = this.$refs.customerNameField;
				if (field && typeof field.focus === "function") {
					field.focus();
				}
			}
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
			this.customer_name = "";
			this.tax_id = "";
			this.mobile_no = "";
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
							const label = `${t.name} (${disc}% ${frappe._("discount") || "скидка"} / ${pts}% ${frappe._("points") || "баллы"})`;
							return {
								name: t.name,
								label: label,
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
		formatBirthdayOnInput() {
			// Handle 8-digit format (DDMMYYYY)
			if (this.birthday && /^\d{8}$/.test(this.birthday)) {
				try {
					const day = this.birthday.substring(0, 2);
					const month = this.birthday.substring(2, 4);
					const year = this.birthday.substring(4);
					this.birthday = `${day}-${month}-${year}`;
				} catch (error) {
					console.error("Error formatting date:", error);
				}
			}
		},
		async submit_dialog() {
			const vm = this;
			this.customer_name = (this.customer_name || "").trim();
			this.mobile_no = (this.mobile_no || "").trim();

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

			// Format birthday to YYYY-MM-DD if it exists and is in another format
			let formatted_birthday = null;
			if (this.birthday) {
				try {
					// First check if it's a date without separators (e.g., 04111994 for 04-11-1994)
					if (/^\d{8}$/.test(this.birthday)) {
						const day = this.birthday.substring(0, 2);
						const month = this.birthday.substring(2, 4);
						const year = this.birthday.substring(4);
						formatted_birthday = `${year}-${month}-${day}`;
					}
					// Check if it's in DD-MM-YYYY format
					else if (/^\d{1,2}-\d{1,2}-\d{4}$/.test(this.birthday)) {
						const parts = this.birthday.split("-");
						if (parts.length === 3) {
							const day = parts[0].padStart(2, "0");
							const month = parts[1].padStart(2, "0");
							const year = parts[2];
							formatted_birthday = `${year}-${month}-${day}`;
						}
					}
					// Handle DD/MM/YYYY format
					else if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(this.birthday)) {
						const parts = this.birthday.split("/");
						if (parts.length === 3) {
							const day = parts[0].padStart(2, "0");
							const month = parts[1].padStart(2, "0");
							const year = parts[2];
							formatted_birthday = `${year}-${month}-${day}`;
						}
					}
					// For any other format, try to use the browser's date parsing
					else if (this.birthday) {
						try {
							const date = new Date(this.birthday);
							// Check if the date is valid
							if (!isNaN(date.getTime())) {
								const year = date.getFullYear();
								const month = String(date.getMonth() + 1).padStart(2, "0");
								const day = String(date.getDate()).padStart(2, "0");
								formatted_birthday = `${year}-${month}-${day}`;
							}
						} catch (e) {
							console.error("Failed to parse date:", e);
						}
					}
				} catch (error) {
					console.error("Error formatting date:", error);
					formatted_birthday = null;
				}
			}

			// Create args object to use in callback
			const args = {
				customer_id: this.customer_id,
				customer_name: this.customer_name,
				tax_id: this.tax_id,
				mobile_no: this.mobile_no,
				address_line1: this.address_line1,
				city: this.city,
				country: this.country,
				email_id: this.email_id,
				referral_code: this.referral_code,
				birthday: formatted_birthday || this.birthday,
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
			if (!this.customer_id) {
				let duplicateCustomers = await customersStore.findLocalDuplicateCustomers(args);
				if (!isOffline() && !duplicateCustomers.length) {
					const duplicateResponse = await frappe.call({
						method: "posawesome.posawesome.api.customers.find_duplicate_customers",
						args: {
							customer_name: args.customer_name,
							mobile_no: args.mobile_no,
							email_id: args.email_id,
							tax_id: args.tax_id,
							company: vm.pos_profile.company,
							pos_profile_doc: JSON.stringify(vm.pos_profile),
						},
					});
					duplicateCustomers = duplicateResponse.message || [];
				}

				if (duplicateCustomers.length) {
					const existing = duplicateCustomers[0];
					const existingLabel = existing.customer_name || existing.name;
					const phoneLabel = existing.mobile_no ? ` (${existing.mobile_no})` : "";
					const useExisting = window.confirm(
						__("An existing customer matches these details: {0}{1}. Select it instead?", [
							existingLabel,
							phoneLabel,
						]),
					);
					if (useExisting) {
						await customersStore.addOrUpdateCustomer(existing);
						customersStore.setSelectedCustomer(existing.name);
						vm.toastStore.show({
							title: __("Existing customer selected"),
							color: "info",
						});
						vm.close_dialog();
					} else {
						vm.toastStore.show({
							title: __("Customer was not created. Review the matching details."),
							color: "warning",
						});
					}
					return;
				}
			}

			if (isOffline()) {
				await saveOfflineCustomer({ args: apiArgs });
				vm.toastStore.show({ title: __("Customer saved offline"), color: "warning" });
				args.name = this.customer_name;
				await customersStore.addOrUpdateCustomer({
					name: args.name,
					customer_name: args.customer_name,
					customer_group: args.customer_group,
					mobile_no: args.mobile_no,
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
						this.email_id = data.email_id;
						this.referral_code = data.referral_code;
						this.birthday = data.birthday;
						this.group = data.customer_group;
						this.territory = data.territory;
						this.loyalty_points = data.loyalty_points;
						this.loyalty_program = data.loyalty_program;
						this.gender = data.gender;
					} else {
						// Setup for new customer
						this.clear_customer();
					}
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

<style scoped></style>
