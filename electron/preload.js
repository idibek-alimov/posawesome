const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
	tp809Request: (request) => ipcRenderer.invoke("tp809-request", request),
	printStoreReceipt: (request) => ipcRenderer.invoke("print-store-receipt", request),
	getServerUrl: () => ipcRenderer.invoke("get-server-url"),
	normalizeServerUrl: (value) => ipcRenderer.invoke("normalize-server-url", value),
	setServerUrl: (value) => ipcRenderer.invoke("set-server-url", value),
	retryLoad: () => ipcRenderer.invoke("retry-load"),
	openSettings: () => ipcRenderer.invoke("open-settings"),
	probeServer: () => ipcRenderer.invoke("probe-server"),
	resetServer: () => ipcRenderer.invoke("reset-server"),
});
