const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const vm = require("node:vm");
const { EventEmitter } = require("node:events");
const { createRequire } = require("node:module");
const http = require("node:http");

function runtime() {
	const windows = [];
	const handlers = new Map();
	const journal = new Map([["serverUrl", "https://shop.example.com/app/posapp"]]);
	const store = { get: (key, fallback) => journal.has(key) ? journal.get(key) : fallback, set: (key, value) => journal.set(key, value), delete: (key) => journal.delete(key) };
	class Window extends EventEmitter {
		constructor(options) { super(); this.options = options; this.webContents = new EventEmitter(); this.webContents.mainFrame = { url: "" }; this.webContents.setWindowOpenHandler = () => {}; this.webContents.session = { setPermissionRequestHandler() {} }; this.destroyed = false; windows.push(this); }
		loadURL(url) { this.webContents.mainFrame.url = url; return Promise.resolve(); }
		loadFile(file) { return this.loadURL(pathToFileURL(file).href); }
		isDestroyed() { return this.destroyed; }
		close() { this.destroyed = true; this.emit("closed"); }
		show() {}
		focus() {}
	}
	const electron = {
		app: { requestSingleInstanceLock: () => true, on() {}, whenReady: () => ({ then: () => ({ catch() {} }) }) },
		BrowserWindow: Window,
		ipcMain: { handle: (channel, callback) => handlers.set(channel, callback) },
		Menu: { buildFromTemplate: (value) => value, setApplicationMenu() {} },
		shell: { openExternal() {} }, net: {}, dialog: {},
	};
	const entry = path.resolve(__dirname, "../electron/main.js");
	const localRequire = createRequire(entry);
	const context = vm.createContext({ require: (name) => name === "electron" ? electron : localRequire(name), __dirname: path.dirname(entry), console, URL, AbortSignal, testStore: store });
	vm.runInContext(readFileSync(entry, "utf8"), context);
	vm.runInContext("store = testStore; registerHandlers(); createWindow();", context);
	return { windows, handlers, store, context, electron, invoke: (channel, win, value, frame = win.webContents.mainFrame) => handlers.get(channel)({ sender: win.webContents, senderFrame: frame }, value) };
}

test("remote POS cannot change server or printer configuration through privileged IPC", async () => {
	const app = runtime();
	const main = app.windows[0];
	await assert.rejects(app.invoke("set-server-url", main, { serverUrl: "https://other.example.com", pin: "123456" }), /cannot access/);
	await assert.rejects(app.invoke("set-printer-settings", main, "http://192.168.1.101:8002"), /cannot access/);
	await assert.rejects(app.invoke("get-server-url", main, undefined, { url: main.webContents.mainFrame.url }), /main frame/);
	main.webContents.mainFrame.url = "https://attacker.example.com";
	await assert.rejects(app.invoke("tp809-request", main, {}), /cannot access/);
});

test("printer settings open without replacing POS and cancel setup does not reload it", async () => {
	const app = runtime();
	const main = app.windows[0];
	const current = main.webContents.mainFrame.url;
	await app.invoke("open-printer-settings", main);
	const printer = app.windows[1];
	assert.match(printer.webContents.mainFrame.url, /printer.html$/);
	await app.invoke("set-printer-settings", printer, "http://192.168.1.101:8002");
	assert.equal(main.webContents.mainFrame.url, current);
	assert.equal(main.options.webPreferences.sandbox, true);
	assert.equal((await app.invoke("get-printer-settings", printer)).printerUrl, "http://192.168.1.101:8002");
	await app.invoke("open-settings", main);
	const settings = app.windows[2];
	await app.invoke("close-settings", settings);
	assert.equal(settings.isDestroyed(), true);
	assert.equal(main.webContents.mainFrame.url, current);
});

test("subresource failure does not replace checkout with the offline page", () => {
	const app = runtime();
	const main = app.windows[0];
	const current = main.webContents.mainFrame.url;
	main.webContents.emit("did-fail-load", {}, -105, "failed image", "https://shop.example.com/image.png", false);
	assert.equal(main.webContents.mainFrame.url, current);
});

test("connection testing reads status without printing, opening a shift or changing the address", async () => {
	const calls = [];
	const server = http.createServer((request, response) => {
		let body = "";
		request.on("data", (chunk) => { body += chunk; });
		request.on("end", () => {
			calls.push({ path: request.url, body: JSON.parse(body) });
			response.end(JSON.stringify({ rc: "SUCCESS", data: { shiftStatus: true, blocked: true, reasonForBlocking: "Test reason" } }));
		});
	});
	await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
	try {
		const app = runtime();
		await app.invoke("open-printer-settings", app.windows[0]);
		const settings = app.windows[1];
		const result = await app.invoke("test-printer", settings, `http://127.0.0.1:${server.address().port}`);
		assert.equal(result.connected, true);
		assert.equal(result.blocked, true);
		assert.deepEqual(calls, [{ path: "/api/deviceStatus", body: { formCode: "DEVICE_STATUS", shouldPrintSlip: false } }]);
		assert.equal((await app.invoke("get-printer-settings", settings)).printerUrl, "");
	} finally { server.close(); }
});

test("ordinary exit leaves shift operations alone and remembers the dismissed explanation", async () => {
	const app = runtime();
	let explanations = 0;
	app.electron.dialog.showMessageBox = async () => { explanations += 1; return { response: 0, checkboxChecked: true }; };
	let prevented = false;
	await app.windows[0].listeners("close")[0]({ preventDefault() { prevented = true; } });
	assert.equal(prevented, true);
	assert.equal(explanations, 1);
	assert.equal(app.store.get("hideExitHint"), true);
	assert.equal(app.windows[0].isDestroyed(), true);
	assert.equal(app.store.get("serverUrl"), "https://shop.example.com/app/posapp");
});
