const path = require("node:path");
const fs = require("node:fs");
const assert = require("node:assert/strict");
const asar = require("../electron/node_modules/@electron/asar");
const root = path.resolve(__dirname, "..");
const archive = path.join(root, "dist-electron/win-unpacked/resources/app.asar");
const files = asar.listPackage(archive).map((file) => file.replaceAll("\\", "/"));
assert(files.some((file) => file.includes("/node_modules/electron-store/")));
for (const moduleName of ["vue", "vite", "electron-builder", "typescript", "electron"]) {
	assert(!files.some((file) => file.startsWith(`/node_modules/${moduleName}/`)), `${moduleName} must not ship`);
}
for (const file of ["main.js", "preload.js", "settings.js", "fiscal.js", "receipt.js", "renderer/ui.js", "renderer/desktop.css", "renderer/printer.js", "renderer/printer.html", "renderer/setup.js", "renderer/setup.html", "renderer/offline.js", "renderer/offline.html"]) {
	assert.equal(asar.extractFile(archive, file).toString(), fs.readFileSync(path.join(root, "electron", file), "utf8"), `${file} differs from source`);
}
const manifest = JSON.parse(asar.extractFile(archive, "package.json"));
assert.equal(manifest.name, "posawesome");
assert.equal(manifest.version, require("../package.json").version);
console.log("Verified packaged source files, stable app identity, production store dependency, and exclusion of frontend/build tools.");
