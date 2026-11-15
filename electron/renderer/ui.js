const translations = {
	ru: {
		close: "Закрыть", setup: "Настройка подключения", setupHint: "Введите адрес ERPNext вашего магазина. Эти настройки выполняет установщик.",
		server: "Адрес ERPNext", pin: "PIN установщика", pinNew: "Создайте PIN установщика (не менее 6 символов). Сохраните его для изменения сервера.",
		pinExisting: "Для изменения адреса нужен PIN установщика.", launch: "Сохранить и открыть кассу", cancel: "Отмена", saved: "Настройки сохранены.",
		printer: "Подключение принтера", printerHint: "Если адрес принтера изменился, укажите новый. Корзина и смена останутся открытыми.",
		address: "Адрес фискального принтера", test: "Проверить подключение", save: "Сохранить", defaults: "Использовать адрес из ERPNext",
		checking: "Проверяем подключение…", connected: "Принтер подключён. Проверка не печатает чек.",
		blocked: "Принтер доступен, но заблокирован.", addressSaved: "Адрес сохранён. Можно продолжить работу без перезапуска кассы.",
		defaultSaved: "Локальный адрес сброшен. Используется адрес из ERPNext.", failed: "Не удалось выполнить действие. Проверьте настройки.",
		offline: "Нет подключения к серверу", offlineHint: "Если касса ещё не подготовлена к автономной работе, подключитесь к серверу. Сохранённые продажи не удаляются.",
		retry: "Повторить подключение", serverSettings: "Настройка сервера", overrideHint: "На этом компьютере используется сохранённый адрес. Настройки ERPNext его не заменят.",
	},
	tg: {
		close: "Пӯшидан", setup: "Танзими пайвастшавӣ", setupHint: "Суроғаи ERPNext-и мағозаро ворид кунед. Ин танзимотро насбкунанда иҷро мекунад.",
		server: "Суроғаи ERPNext", pin: "PIN-и насбкунанда", pinNew: "PIN-и насбкунандаро созед (на камтар аз 6 аломат). Онро барои иваз кардани сервер нигоҳ доред.",
		pinExisting: "Барои иваз кардани суроға PIN-и насбкунанда лозим аст.", launch: "Сабт ва кушодани хазина", cancel: "Бекор кардан", saved: "Танзимот сабт шуд.",
		printer: "Пайвастшавии чопгар", printerHint: "Агар суроғаи чопгар иваз шуда бошад, суроғаи навро ворид кунед. Сабад ва баст кушода мемонанд.",
		address: "Суроғаи чопгари фискалӣ", test: "Санҷидани пайвастшавӣ", save: "Сабт кардан", defaults: "Истифодаи суроға аз ERPNext",
		checking: "Пайвастшавӣ санҷида мешавад…", connected: "Чопгар пайваст аст. Санҷиш расидро чоп намекунад.",
		blocked: "Чопгар дастрас аст, аммо баста шудааст.", addressSaved: "Суроға сабт шуд. Корро бе аз нав оғоз кардани хазина идома диҳед.",
		defaultSaved: "Суроғаи маҳаллӣ тоза шуд. Суроғаи ERPNext истифода мешавад.", failed: "Амал иҷро нашуд. Танзимотро санҷед.",
		offline: "Пайвастшавӣ бо сервер нест", offlineHint: "Агар хазина ҳанӯз барои кори автономӣ омода набошад, ба сервер пайваст шавед. Фурӯшҳои сабтшуда нест намешаванд.",
		retry: "Аз нав пайваст шудан", serverSettings: "Танзими сервер", overrideHint: "Дар ин компютер суроғаи сабтшуда истифода мешавад. ERPNext онро иваз намекунад.",
	},
};
let language = localStorage.getItem("desktop-language") === "tg" ? "tg" : "ru";
window.desktopText = (key) => translations[language][key] || key;
window.setDesktopStatus = (text, tone = "", key = "") => {
	const status = document.getElementById("status");
	status.textContent = text;
	status.dataset.tone = tone;
	if (key) status.dataset.text = key;
	else delete status.dataset.text;
};
function applyLanguage() {
	document.documentElement.lang = language;
	document.querySelectorAll("[data-text]").forEach((element) => { element.textContent = window.desktopText(element.dataset.text); });
}
document.querySelectorAll("[data-language]").forEach((button) => button.addEventListener("click", () => {
	language = button.dataset.language;
	localStorage.setItem("desktop-language", language);
	applyLanguage();
}));
applyLanguage();
