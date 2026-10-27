import { ref, computed } from "vue";
import { useToastStore } from "../../../stores/toastStore";

declare const frappe: any;
declare const __: (_str: string, _args?: any[]) => string;

const managerUnlocked = ref(false);
const managerName = ref("");
const managerCountdown = ref(0);
const badgeDialogOpen = ref(false);
let countdownTimer: any = null;

export function useManagerAuthorization() {
	const toastStore = useToastStore();

	const isUnlocked = computed(() => managerUnlocked.value);

	const startUnlockTimer = (seconds = 60, name = "Администратор") => {
		if (countdownTimer) {
			clearInterval(countdownTimer);
			countdownTimer = null;
		}

		managerUnlocked.value = true;
		managerName.value = name;
		managerCountdown.value = seconds;

		countdownTimer = setInterval(() => {
			managerCountdown.value -= 1;
			if (managerCountdown.value <= 0) {
				clearInterval(countdownTimer);
				countdownTimer = null;
				managerUnlocked.value = false;
				managerName.value = "";
				toastStore.show({
					title: __("Время авторизации администратора истекло (60 сек)"),
					color: "info",
				});
			}
		}, 1000);
	};

	const unlockManually = (name = "Администратор") => {
		startUnlockTimer(60, name);
	};

	const verifyBadge = async (badgeCode: string): Promise<boolean> => {
		const code = (badgeCode || "").trim();
		if (!code) return false;

		try {
			const res = await frappe.call("posawesome.posawesome.api.fiscal.verify_manager_badge", {
				badge_code: code,
			});

			const data = res?.message || {};
			if (data.valid) {
				const mgrName = data.manager_name || "Администратор";
				startUnlockTimer(data.duration_seconds || 60, mgrName);
				badgeDialogOpen.value = false;

				toastStore.show({
					title: `🔓 ${__("Режим администратора активен: {0}. Скидки доступны 60 сек", [mgrName])}`,
					color: "success",
				});

				if (typeof frappe !== "undefined" && frappe.utils?.play_sound) {
					frappe.utils.play_sound("submit");
				}
				return true;
			} else {
				toastStore.show({
					title: data.message || __("Штрихкод не авторизован"),
					color: "error",
				});
				if (typeof frappe !== "undefined" && frappe.utils?.play_sound) {
					frappe.utils.play_sound("error");
				}
				return false;
			}
		} catch (err: any) {
			toastStore.show({
				title: err?.message || __("Ошибка проверки штрихкода администратора"),
				color: "error",
			});
			return false;
		}
	};

	/**
	 * Intercept scanner barcode: returns true if code was handled as manager badge
	 */
	const handlePotentialManagerBarcode = (code: string): boolean => {
		if (!code) return false;
		const trimmed = code.trim();
		if (trimmed.toUpperCase().startsWith("MGR-")) {
			verifyBadge(trimmed);
			return true;
		}
		return false;
	};

	/**
	 * Check if discount modification is allowed; if not, open badge prompt dialog
	 */
	const requireManagerForDiscount = (isSupervisor = false): boolean => {
		if (isSupervisor || managerUnlocked.value) {
			return true;
		}
		badgeDialogOpen.value = true;
		toastStore.show({
			title: __("🔒 Требуется авторизация. Отсканируйте штрихкод администратора"),
			color: "warning",
		});
		return false;
	};

	return {
		managerUnlocked: isUnlocked,
		managerName,
		managerCountdown,
		badgeDialogOpen,
		startUnlockTimer,
		unlockManually,
		verifyBadge,
		handlePotentialManagerBarcode,
		requireManagerForDiscount,
	};
}
