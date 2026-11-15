const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
	tp809Request: (request) => ipcRenderer.invoke("tp809-request", request),
	printStoreReceipt: (request) => ipcRenderer.invoke("print-store-receipt", request),
	getServerUrl: () => ipcRenderer.invoke("get-server-url"),
	normalizeServerUrl: (value) => ipcRenderer.invoke("normalize-server-url", value),
	getInstallationSettings: () => ipcRenderer.invoke("get-installation-settings"),
	setServerUrl: (settings) => ipcRenderer.invoke("set-server-url", settings),
	openPrinterSettings: () => ipcRenderer.invoke("open-printer-settings"),
	getPrinterSettings: () => ipcRenderer.invoke("get-printer-settings"),
	setPrinterSettings: (value) => ipcRenderer.invoke("set-printer-settings", value),
	testPrinter: (value) => ipcRenderer.invoke("test-printer", value),
	retryLoad: () => ipcRenderer.invoke("retry-load"),
	openSettings: () => ipcRenderer.invoke("open-settings"),
	closeSettings: () => ipcRenderer.invoke("close-settings"),
	probeServer: () => ipcRenderer.invoke("probe-server"),
});
