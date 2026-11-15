const path = require("node:path");
const { spawnSync } = require("node:child_process");
const root = path.resolve(__dirname, "..");
const project = require(path.join(root, "package.json"));
const desktop = require(path.join(root, "electron/package.json"));
if (desktop.version !== project.version) throw new Error("Desktop and application versions must match before packaging");
const cli = path.join(root, "electron/node_modules/electron-builder/cli.js");
const args = process.argv.slice(2);
const target = args.includes("--win") ? "win32" : args.includes("--linux") ? "linux" : args.includes("--mac") ? "darwin" : process.platform;
const result = spawnSync(process.execPath, [
	cli,
	`--config.electronVersion=${desktop.devDependencies.electron}`,
	...(target === process.platform ? [`--config.electronDist=${path.join(root, "electron/node_modules/electron/dist")}`] : []),
	...args,
], { cwd: root, stdio: "inherit", env: { ...process.env, ELECTRON_BUILDER_CACHE: process.env.ELECTRON_BUILDER_CACHE || path.join(root, ".desktop-cache") } });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
