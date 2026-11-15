const { createHash, randomBytes, scryptSync, timingSafeEqual } = require("node:crypto");
const { printerUrl } = require("./fiscal");

function ensureUrl(value) {
	if (typeof value !== "string" || !value.trim()) return "";
	try {
		const raw = value.trim();
		const url = new URL(raw.includes("://") ? raw : `https://${raw}`);
		if (!["https:", "http:"].includes(url.protocol) || !url.hostname || url.username || url.password) return "";
		if (url.protocol === "http:") printerUrl(url.origin, "deviceStatus");
		if (!["", "/", "/app/posapp", "/app/posapp/", "/app/posawesome", "/app/posawesome/"].includes(url.pathname)) return "";
		url.pathname = "/app/posapp";
		url.search = "";
		url.hash = "";
		return url.toString();
	} catch {
		return "";
	}
}

function connectionKey(serverUrl) {
	const normalized = ensureUrl(serverUrl);
	if (!normalized) throw new Error("Configure a valid ERPNext server first");
	return `connections.${createHash("sha256").update(new URL(normalized).origin).digest("hex")}`;
}

function normalizePrinterUrl(value) {
	if (typeof value !== "string" || !value.trim()) return "";
	const raw = value.trim();
	return printerUrl(raw.includes("://") ? raw : `http://${raw}`, "deviceStatus").origin;
}

function getPrinterSettings(store) {
	const serverUrl = ensureUrl(store.get("serverUrl", ""));
	if (!serverUrl) return { serverUrl: "", printerUrl: "", defaultPrinterUrl: "" };
	const key = connectionKey(serverUrl);
	const override = store.get(`${key}.printerUrl`, "");
	const defaultPrinterUrl = store.get(`${key}.defaultPrinterUrl`, "");
	return { serverUrl, printerUrl: override || defaultPrinterUrl, defaultPrinterUrl, overridden: Boolean(override) };
}

function setPrinterSettings(store, value) {
	const printer = normalizePrinterUrl(value);
	const key = connectionKey(store.get("serverUrl", ""));
	if (printer) store.set(`${key}.printerUrl`, printer);
	else store.delete(`${key}.printerUrl`);
	return getPrinterSettings(store);
}

function resolvePrinterRequest(store, request) {
	if (!request || typeof request !== "object") throw new Error("Invalid fiscal request");
	const key = connectionKey(store.get("serverUrl", ""));
	if (request.printer_url) {
		const printer = normalizePrinterUrl(request.printer_url);
		if (store.get(`${key}.defaultPrinterUrl`, "") !== printer) store.set(`${key}.defaultPrinterUrl`, printer);
	}
	const settings = getPrinterSettings(store);
	if (!settings.printerUrl) throw new Error("Configure the fiscal printer address in Printer connection");
	return { ...request, printer_url: settings.printerUrl };
}

function pinDigest(pin, salt) {
	if (typeof pin !== "string" || pin.length < 6 || pin.length > 128) throw new Error("Use an installation PIN of at least 6 characters");
	return scryptSync(pin, salt, 32);
}

function authorizeInstallation(store, pin) {
	const saved = store.get("installationPin", null);
	if (!saved) return false;
	const digest = pinDigest(pin, saved.salt);
	if (!timingSafeEqual(digest, Buffer.from(saved.hash, "hex"))) throw new Error("Incorrect installation PIN");
	return true;
}

function saveServerSettings(store, { serverUrl, pin } = {}) {
	const normalized = ensureUrl(serverUrl);
	if (!normalized) throw new Error("Enter an HTTPS ERPNext address, or an HTTP address on the local network");
	if (!authorizeInstallation(store, pin)) {
		const salt = randomBytes(16).toString("hex");
		store.set("installationPin", { salt, hash: pinDigest(pin, salt).toString("hex") });
	}
	store.set("serverUrl", normalized);
	return normalized;
}

module.exports = { ensureUrl, connectionKey, normalizePrinterUrl, getPrinterSettings, setPrinterSettings, resolvePrinterRequest, authorizeInstallation, saveServerSettings };
