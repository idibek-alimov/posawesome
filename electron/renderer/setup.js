const serverInput = document.getElementById("server-url");
const pinInput = document.getElementById("installation-pin");
const form = document.getElementById("server-form");
window.electronAPI.getInstallationSettings().then((settings) => {
	serverInput.value = settings.serverUrl;
	const hint = document.getElementById("pin-hint");
	hint.dataset.text = settings.protected ? "pinExisting" : "pinNew";
	hint.textContent = window.desktopText(hint.dataset.text);
	document.getElementById("open-saved").hidden = !settings.serverUrl;
}).catch((error) => window.setDesktopStatus(error.message, "error"));
form.addEventListener("submit", async (event) => {
	event.preventDefault();
	const button = form.querySelector("button[type=submit]");
	button.disabled = true;
	try {
		await window.electronAPI.setServerUrl({ serverUrl: serverInput.value, pin: pinInput.value });
		pinInput.value = "";
	} catch (error) { window.setDesktopStatus(error.message, "error"); }
	finally { button.disabled = false; }
});
document.getElementById("open-saved").addEventListener("click", () => {
	window.electronAPI.closeSettings().catch((error) => window.setDesktopStatus(error.message, "error"));
});
