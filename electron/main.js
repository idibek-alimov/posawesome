const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { app, BrowserWindow, ipcMain, net, shell, Menu, dialog } = require("electron");
const { fiscalRequest } = require("./fiscal");
const { printReceipt } = require("./receipt");
const { ensureUrl, getPrinterSettings, setPrinterSettings, resolvePrinterRequest, normalizePrinterUrl, saveServerSettings } = require("./settings");

let store;
let mainWindow;
let settingsWindow;
let printerWindow;
let exitConfirmed = false;
let exitDialogOpen = false;

const localPage = (name) => path.join(__dirname, "renderer", name);
const localUrl = (name) => pathToFileURL(localPage(name)).href;
const getStoredUrl = () => ensureUrl(store.get("serverUrl", ""));

function assertSender(event, { pos = false, pages = [] } = {}) {
	const frame = event.senderFrame;
	if (!frame || frame !== event.sender.mainFrame) throw new Error("This operation requires the application main frame");
	const windows = [mainWindow, settingsWindow, printerWindow].filter((win) => win && !win.isDestroyed());
	if (!windows.some((win) => win.webContents === event.sender)) throw new Error("Unknown application window");
	if (pages.some((name) => frame.url === localUrl(name))) return;
	if (pos && event.sender === mainWindow?.webContents && getStoredUrl()) {
		const sender = new URL(frame.url);
		if (["http:", "https:"].includes(sender.protocol) && sender.origin === new URL(getStoredUrl()).origin) return;
	}
	throw new Error("This page cannot access the requested desktop operation");
}

function configureWindow(win, allowedLocalPages = []) {
	win.webContents.setWindowOpenHandler(({ url }) => {
		if (/^https?:\/\//.test(url)) void shell.openExternal(url);
		return { action: "deny" };
	});
	const guard = (event, target) => {
		const allowedFile = allowedLocalPages.some((name) => target === localUrl(name));
		let allowedServer = false;
		try { allowedServer = Boolean(getStoredUrl()) && new URL(target).origin === new URL(getStoredUrl()).origin; } catch {}
		if (!allowedFile && !(win === mainWindow && allowedServer)) event.preventDefault();
	};
	win.webContents.on("will-navigate", guard);
	win.webContents.on("will-redirect", guard);
	win.webContents.session.setPermissionRequestHandler(async (contents, permission, callback, details) => {
		let fromPos = false;
		try { fromPos = contents === mainWindow?.webContents && Boolean(getStoredUrl()) && new URL(details.requestingUrl).origin === new URL(getStoredUrl()).origin; } catch {}
		if (!fromPos || permission !== "media" || !details.mediaTypes?.length || details.mediaTypes.some((type) => type !== "video")) return callback(false);
		try {
			const result = await dialog.showMessageBox(mainWindow, { type: "question", title: "Камера", message: "Разрешить кассе использовать камеру для сканирования?", buttons: ["Разрешить", "Отмена"], defaultId: 1, cancelId: 1 });
			callback(result.response === 0);
		} catch { callback(false); }
	});
}

function openLocalWindow(kind) {
	const printer = kind === "printer";
	let win = printer ? printerWindow : settingsWindow;
	if (win && !win.isDestroyed()) { win.focus(); return; }
	win = new BrowserWindow({
		parent: mainWindow, modal: true, width: 660, height: 680,
		minWidth: 480, minHeight: 500, autoHideMenuBar: true,
		title: printer ? "Подключение принтера" : "Настройка подключения",
		webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
	});
	if (printer) printerWindow = win;
	else settingsWindow = win;
	configureWindow(win, [printer ? "printer.html" : "setup.html"]);
	win.on("closed", () => { if (printer) printerWindow = null; else settingsWindow = null; });
	void win.loadFile(localPage(printer ? "printer.html" : "setup.html"));
}

function loadServer() {
	const target = getStoredUrl();
	if (!target) return mainWindow.loadFile(localPage("setup.html"));
	return mainWindow.loadURL(target).catch((error) => console.warn("POS navigation failed:", error.code || error.message));
}

function createWindow() {
	mainWindow = new BrowserWindow({
		height: 900, width: 1400, minWidth: 1024, minHeight: 700,
		title: "Radolfa Desktop", backgroundColor: "#f5f7fa", show: false,
		webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false },
	});
	configureWindow(mainWindow, ["setup.html", "offline.html"]);
	mainWindow.webContents.on("did-fail-load", (_event, code, _description, _url, isMainFrame) => {
		if (!isMainFrame || code === -3) return;
		void mainWindow.loadFile(localPage("offline.html"));
	});
	mainWindow.once("ready-to-show", () => mainWindow.show());
	mainWindow.on("close", async (event) => {
		if (exitConfirmed || store.get("hideExitHint", false)) return;
		event.preventDefault();
		if (exitDialogOpen) return;
		exitDialogOpen = true;
		try {
			const result = await dialog.showMessageBox(mainWindow, {
				type: "info", title: "Выход из кассы", message: "Смена останется открытой.",
				detail: "Чтобы завершить рабочий день, используйте «Закрыть смену» в кассе.",
				buttons: ["Выйти", "Остаться"], defaultId: 0, cancelId: 1,
				checkboxLabel: "Больше не показывать", checkboxChecked: false,
			});
			if (result.response === 0) {
				if (result.checkboxChecked) store.set("hideExitHint", true);
				exitConfirmed = true;
				mainWindow.close();
			}
		} finally { exitDialogOpen = false; }
	});
	Menu.setApplicationMenu(Menu.buildFromTemplate([
		{ label: "Radolfa", submenu: [
			{ label: "Подключение принтера", accelerator: "CmdOrCtrl+Shift+P", click: () => openLocalWindow("printer") },
			{ label: "Настройка сервера", click: () => openLocalWindow("setup") },
			{ type: "separator" }, { role: "quit", label: "Выйти" },
		] },
		{ role: "editMenu" },
		{ label: "Вид", submenu: [{ role: "togglefullscreen" }, { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }] },
	]));
	void loadServer();
}

function registerHandlers() {
	const localPages = ["setup.html", "offline.html", "printer.html"];
	const handle = (channel, access, callback) => ipcMain.handle(channel, async (event, ...args) => {
		assertSender(event, access);
		return callback(...args);
	});
	handle("get-server-url", { pages: localPages, pos: true }, () => getStoredUrl());
	handle("get-installation-settings", { pages: ["setup.html"] }, () => ({ serverUrl: getStoredUrl(), protected: Boolean(store.get("installationPin")) }));
	handle("normalize-server-url", { pages: ["setup.html"] }, ensureUrl);
	handle("set-server-url", { pages: ["setup.html"] }, (settings) => {
		const saved = saveServerSettings(store, settings);
		if (settingsWindow && !settingsWindow.isDestroyed()) settingsWindow.close();
		void loadServer();
		return saved;
	});
	handle("retry-load", { pages: ["offline.html", "setup.html"] }, () => { void loadServer(); return { launched: Boolean(getStoredUrl()) }; });
	handle("close-settings", { pages: ["setup.html"] }, () => {
		if (settingsWindow && !settingsWindow.isDestroyed()) settingsWindow.close();
		else if (getStoredUrl()) void loadServer();
	});
	handle("open-settings", { pages: localPages, pos: true }, () => { openLocalWindow("setup"); return { opened: true }; });
	handle("open-printer-settings", { pages: localPages, pos: true }, () => { openLocalWindow("printer"); return { opened: true }; });
	handle("get-printer-settings", { pages: ["printer.html", "setup.html"], pos: true }, () => getPrinterSettings(store));
	handle("set-printer-settings", { pages: ["printer.html"] }, (value) => setPrinterSettings(store, value));
	handle("test-printer", { pages: ["printer.html"] }, async (value) => {
		const printer = normalizePrinterUrl(value);
		if (!printer) throw new Error("Укажите адрес принтера");
		const result = await fiscalRequest(store, { printer_url: printer, endpoint: "deviceStatus", payload: { formCode: "DEVICE_STATUS", shouldPrintSlip: false } });
		if (result.rc !== "SUCCESS") throw new Error(result.rc || "Принтер не подтвердил подключение");
		if (!result.data || typeof result.data.shiftStatus !== "boolean" || typeof result.data.blocked !== "boolean") throw new Error("Принтер вернул неполный статус");
		return { connected: true, blocked: result.data.blocked, shiftOpen: result.data.shiftStatus, reason: String(result.data.reasonForBlocking || "") };
	});
	handle("tp809-request", { pos: true }, (request) => fiscalRequest(store, resolvePrinterRequest(store, request)));
	handle("print-store-receipt", { pos: true }, (request) => printReceipt(BrowserWindow, request));
	handle("probe-server", { pages: localPages, pos: true }, async () => {
		if (!getStoredUrl()) return { reachable: false };
		try {
			const response = await net.fetch(getStoredUrl(), { method: "HEAD", signal: AbortSignal.timeout(8000) });
			return { reachable: response.ok, status: response.status };
		} catch { return { reachable: false }; }
	});
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
	app.on("second-instance", () => { if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.focus(); } });
	app.on("window-all-closed", () => app.quit());
	app.whenReady().then(async () => {
		const { default: Store } = await import("electron-store");
		store = new Store({ name: "posawesome-desktop", defaults: { serverUrl: "" } });
		app.setAppUserModelId("com.posawesome.desktop");
		registerHandlers();
		createWindow();
	}).catch((error) => { console.error("Desktop startup failed", error); dialog.showErrorBox("POS Awesome", error.message); app.quit(); });
}
