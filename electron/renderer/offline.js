document.getElementById("retry").addEventListener("click", () => window.electronAPI.retryLoad().catch((error) => window.setDesktopStatus(error.message, "error")));
document.getElementById("settings").addEventListener("click", () => window.electronAPI.openSettings());
document.getElementById("printer").addEventListener("click", () => window.electronAPI.openPrinterSettings());
window.electronAPI.getServerUrl().then((server) => { document.getElementById("status").textContent = server; });
