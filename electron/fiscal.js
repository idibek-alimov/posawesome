const http = require("node:http");
const https = require("node:https");

const ENDPOINTS = new Set(["formReceipt", "getFDByNumber", "deviceStatus", "openShift", "closeShift"]);

function printerUrl(value, endpoint) {
	const url = new URL(value);
	const host = url.hostname;
	const local = /^(localhost|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$/.test(host) || host.endsWith(".local");
	if (!local || !["http:", "https:"].includes(url.protocol) || url.username || url.password || !ENDPOINTS.has(endpoint)) {
		throw new Error("Configure a local TP809 URL and supported fiscal operation");
	}
	url.pathname = `/api/${endpoint}`;
	url.search = "";
	url.hash = "";
	return url;
}

function send(url, payload) {
	return new Promise((resolve, reject) => {
		const body = JSON.stringify(payload);
		const req = (url.protocol === "https:" ? https : http).request(url, {
			method: "POST", headers: { "Content-Type": "application/json; charset=utf-8", "Content-Length": Buffer.byteLength(body) },
		}, (response) => {
			let data = "";
			response.on("data", (chunk) => {
				data += chunk;
				if (data.length > 1024 * 1024) req.destroy(new Error("Fiscal response too large"));
			});
			response.on("end", () => {
				try {
					if (response.statusCode !== 200) throw new Error(`Fiscal HTTP ${response.statusCode}`);
					resolve(JSON.parse(data));
				} catch (error) { reject(error); }
			});
		});
		req.setTimeout(15000, () => req.destroy(new Error("Fiscal result unknown: printer timeout")));
		req.on("error", reject);
		req.end(body);
	});
}

async function fiscalRequest(store, { printer_url, endpoint, payload, attempt }) {
	const url = printerUrl(printer_url, endpoint);
	const isReceipt = endpoint === "formReceipt";
	const key = `fiscalAttempts.${attempt}`;
	if (isReceipt) {
		if (!/^[a-zA-Z0-9]{16,64}$/.test(attempt || "")) throw new Error("Prepared fiscal attempt required");
		const prior = store.get(key);
		if (prior?.result) return prior.result;
		if (prior) throw new Error("Fiscal result unknown. Reconcile the printer journal.");
		// Persist before network I/O: process crashes cannot trigger automatic resend.
		store.set(key, { state: "unknown", invoice: payload?.receiptSum });
	}
	const result = await send(url, payload);
	if (isReceipt) store.set(key, { result });
	return result;
}

module.exports = { fiscalRequest, printerUrl };
