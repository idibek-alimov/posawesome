/** Ordinary receipts use the OS driver; this module never calls the fiscal API. */
async function printReceipt(BrowserWindow, { html, printerName = "", silent = false } = {}) {
	if (typeof html !== "string" || !html.startsWith('<!doctype html><html lang="tg"><head>') || Buffer.byteLength(html) > 1024 * 1024) {
		throw new Error("Invalid store receipt");
	}
	const win = new BrowserWindow({ show: false, width: 400, height: 700,
		webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true } });
	try {
		win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
		// Deny script, remote resources and navigation in the print-only document.
		const secured = html.replace("<head>", '<head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; font-src data:;">');
		await win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(secured)}`);
		win.webContents.on("will-navigate", event => event.preventDefault());
		if (printerName) {
			const printers = await win.webContents.getPrintersAsync();
			if (!printers.some(p => p.name === printerName)) throw new Error("Configured receipt printer is not installed on this computer");
		}
		const height = await win.webContents.executeJavaScript("document.fonts.ready.then(() => document.body.scrollHeight)");
		if (!Number.isFinite(height) || height <= 0 || height > 11000) throw new Error("Receipt is too long for one thermal page");
		await new Promise((resolve, reject) => win.webContents.print({
			silent: Boolean(silent && printerName), deviceName: printerName || undefined,
			printBackground: false, color: false, copies: 1, margins: { marginType: "none" },
			pageSize: { width: 80000, height: Math.max(10000, Math.ceil(height * 25400 / 96) + 2000) },
		}, (success, reason) => success ? resolve() : reject(new Error(reason || "Receipt print job was not accepted"))));
		return { accepted: true };
	} finally { win.destroy(); }
}

module.exports = { printReceipt };
