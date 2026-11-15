const { test } = require("node:test");
const assert = require("node:assert/strict");
const { ensureUrl, normalizePrinterUrl, getPrinterSettings, setPrinterSettings, resolvePrinterRequest, saveServerSettings } = require("../electron/settings");

function makeStore(initial = {}) {
	const data = new Map(Object.entries(initial));
	return { get: (key, fallback) => data.has(key) ? data.get(key) : fallback, set: (key, value) => data.set(key, value), delete: (key) => data.delete(key) };
}

test("server setup normalizes POS routes and rejects unsafe URLs", () => {
	assert.equal(ensureUrl(" shop.example.com "), "https://shop.example.com/app/posapp");
	assert.equal(ensureUrl("https://shop.example.com/app/posawesome/"), "https://shop.example.com/app/posapp");
	assert.equal(ensureUrl("http://127.0.0.1:8088"), "http://127.0.0.1:8088/app/posapp");
	for (const value of ["javascript:alert(1)", "file:///C:/app", "ftp://shop.example.com", "https://admin:secret@shop.example.com", "http://public.example.com", "https://shop.example.com/login", null]) assert.equal(ensureUrl(value), "");
});

test("printer address editing is local and scoped to the ERPNext site", () => {
	const store = makeStore({ serverUrl: "https://shop-one.example.com" });
	setPrinterSettings(store, "192.168.1.101:8002/");
	assert.equal(getPrinterSettings(store).printerUrl, "http://192.168.1.101:8002");
	store.set("serverUrl", "https://shop-two.example.com");
	assert.equal(getPrinterSettings(store).printerUrl, "");
	store.set("serverUrl", "https://shop-one.example.com");
	assert.equal(getPrinterSettings(store).printerUrl, "http://192.168.1.101:8002");
	assert.throws(() => normalizePrinterUrl("https://public.example.com"));
});

test("a refreshed POS Profile cannot overwrite a working local correction", () => {
	const store = makeStore({ serverUrl: "https://shop.example.com" });
	const request = { printer_url: "http://192.168.1.102:8002/", endpoint: "formReceipt", attempt: "a".repeat(32), payload: { receiptSum: 100 } };
	assert.equal(resolvePrinterRequest(store, request).printer_url, "http://192.168.1.102:8002");
	setPrinterSettings(store, "http://192.168.1.101:8002/");
	const resolved = resolvePrinterRequest(store, request);
	assert.equal(resolved.printer_url, "http://192.168.1.101:8002");
	assert.equal(resolved.payload, request.payload);
	assert.equal(resolved.attempt, request.attempt);
	assert.equal(request.printer_url, "http://192.168.1.102:8002/");
	setPrinterSettings(store, "");
	assert.equal(getPrinterSettings(store).printerUrl, "http://192.168.1.102:8002");
});

test("installation PIN protects server changes without storing the PIN itself", () => {
	const store = makeStore();
	assert.throws(() => saveServerSettings(store, { serverUrl: "https://shop.example.com", pin: "123" }));
	saveServerSettings(store, { serverUrl: "https://shop.example.com", pin: "123456" });
	assert.equal(store.get("serverUrl"), "https://shop.example.com/app/posapp");
	assert.notEqual(store.get("installationPin").hash, "123456");
	assert.throws(() => saveServerSettings(store, { serverUrl: "https://another.example.com", pin: "654321" }), /Incorrect/);
	assert.equal(store.get("serverUrl"), "https://shop.example.com/app/posapp");
	saveServerSettings(store, { serverUrl: "https://another.example.com", pin: "123456" });
	assert.equal(store.get("serverUrl"), "https://another.example.com/app/posapp");
});
