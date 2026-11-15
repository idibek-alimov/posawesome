const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");
const { pathToFileURL } = require("node:url");
const { app } = require("electron");

const previewRoot = path.resolve(__dirname, "../dist-electron");
fs.mkdirSync(previewRoot, { recursive: true });
const profile = fs.mkdtempSync(path.join(previewRoot, "preview-profile-"));
const log = (message) => fs.appendFileSync(path.join(previewRoot, "preview.log"), `${new Date().toISOString()} ${message}\n`);
process.on("uncaughtException", (error) => { log(error.stack); app.exit(1); });
log(`Starting ${process.pid} with profile ${profile}`);
app.setPath("userData", profile);
const server = http.createServer((request, response) => {
	if (request.url === "/api/deviceStatus" && request.method === "POST") {
		response.setHeader("Content-Type", "application/json");
		response.end(JSON.stringify({ rc: "SUCCESS", data: { shiftStatus: true, blocked: false } }));
		return;
	}
	if (request.method !== "GET" || request.url !== "/app/posapp") { response.writeHead(405); response.end(); return; }
	response.setHeader("Content-Type", "text/html; charset=utf-8");
	response.end('<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Radolfa — desktop preview</title></head><body style="font-family:Segoe UI;padding:40px"><h1>Проверка настольного приложения</h1><p>Изолированный пример. Реальные продажи и принтеры не используются.</p><label>Тестовая корзина <input value="Товар — 25 TJS"></label><p><button onclick="electronAPI.openPrinterSettings()">Подключение принтера</button></p><p>Откройте настройки принтера, сохраните адрес и проверьте, что корзина осталась на месте.</p></body></html>');
});
server.listen(0, "127.0.0.1", async () => {
	try {
		await app.whenReady();
		log("Electron ready");
		const { default: Store } = await import(pathToFileURL(path.resolve(__dirname, "../electron/node_modules/electron-store/index.js")).href);
		const store = new Store({ name: "posawesome-desktop" });
		const address = `http://127.0.0.1:${server.address().port}`;
		store.set("serverUrl", `${address}/app/posapp`);
		store.set("hideExitHint", true);
		require("../electron/settings").setPrinterSettings(store, address);
		console.log(`Desktop preview: ${address}; isolated profile: ${profile}`);
		require("../electron/main.js");
		log("Production main loaded");
		setTimeout(() => {
			const { BrowserWindow } = require("electron");
			log(JSON.stringify(BrowserWindow.getAllWindows().map((win) => ({ title: win.getTitle(), url: win.webContents.getURL(), visible: win.isVisible() }))));
		}, 4000);
	} catch (error) { log(error.stack); console.error(error); app.exit(1); }
});
app.on("will-quit", () => server.close());
