const input = document.getElementById("printer-url");
let busy = false;
let currentSettings;
function applySettings(settings) {
	currentSettings = settings;
	input.value = settings.printerUrl;
	document.getElementById("override-hint").hidden = !settings.overridden;
	document.getElementById("use-default").disabled = !settings.overridden || !settings.defaultPrinterUrl;
}
async function act(callback) {
	if (busy) return;
	busy = true;
	document.querySelectorAll("button").forEach((button) => { button.disabled = true; });
	try { await callback(); }
	catch (error) { window.setDesktopStatus(`${window.desktopText("failed")}\n${error.message}`, "error"); }
	finally {
		busy = false;
		document.querySelectorAll("button").forEach((button) => { button.disabled = false; });
		document.getElementById("use-default").disabled = !currentSettings?.overridden || !currentSettings?.defaultPrinterUrl;
	}
}
window.electronAPI.getPrinterSettings().then(applySettings).catch((error) => window.setDesktopStatus(error.message, "error"));
document.getElementById("test").addEventListener("click", () => act(async () => {
	window.setDesktopStatus(window.desktopText("checking"), "", "checking");
	const result = await window.electronAPI.testPrinter(input.value);
	window.setDesktopStatus(result.blocked ? `${window.desktopText("blocked")} ${result.reason}` : window.desktopText("connected"), result.blocked ? "error" : "success", result.blocked ? "" : "connected");
}));
document.getElementById("printer-form").addEventListener("submit", (event) => {
	event.preventDefault();
	void act(async () => {
		applySettings(await window.electronAPI.setPrinterSettings(input.value));
		window.setDesktopStatus(window.desktopText("addressSaved"), "success", "addressSaved");
	});
});
document.getElementById("use-default").addEventListener("click", () => act(async () => {
	applySettings(await window.electronAPI.setPrinterSettings(""));
	window.setDesktopStatus(window.desktopText("defaultSaved"), "success", "defaultSaved");
}));
document.getElementById("close").addEventListener("click", () => window.close());
