const { test } = require('node:test');
const assert = require('node:assert/strict');
const { printReceipt } = require('../electron/receipt');
const html = '<!doctype html><html lang="tg"><head></head><body>РАСИДИ МОЛӢ</body></html>';
function fakeWindow({ printers = ['TP809'], success = true } = {}) {
 let instance;
 class Window {
  constructor(options) {
   instance = this; this.options = options;
   this.webContents = { setWindowOpenHandler: fn => { this.open = fn; }, on: () => {},
    getPrintersAsync: async () => printers.map(name => ({ name })), executeJavaScript: async () => 500,
    print: (options, callback) => { this.printOptions = options; callback(success, 'printer unavailable'); } };
  }
  async loadURL(url) { this.url = url; }
  destroy() { this.destroyed = true; }
 }
 return { Window, get: () => instance };
}
test('store receipt uses isolated native OS printing, correct paper and selected printer', async () => {
 const fake = fakeWindow();
 assert.deepEqual(await printReceipt(fake.Window, { html, printerName: 'TP809', silent: true }), { accepted: true });
 const win = fake.get();
 assert.equal(win.options.webPreferences.nodeIntegration, false); assert.equal(win.options.webPreferences.sandbox, true);
 assert.match(decodeURIComponent(win.url), /default-src 'none'/);
 assert.equal(win.printOptions.deviceName, 'TP809'); assert.equal(win.printOptions.silent, true);
 assert.equal(win.printOptions.pageSize.width, 80000); assert.equal(win.destroyed, true);
});
test('store receipt never silently chooses a different printer and destroys failed windows', async () => {
 const missing = fakeWindow({ printers: [] });
 await assert.rejects(printReceipt(missing.Window, { html, printerName: 'TP809', silent: true }), /not installed/);
 assert.equal(missing.get().printOptions, undefined); assert.equal(missing.get().destroyed, true);
 const noName = fakeWindow(); await printReceipt(noName.Window, { html, silent: true });
 assert.equal(noName.get().printOptions.silent, false);
 const failed = fakeWindow({ success: false });
 await assert.rejects(printReceipt(failed.Window, { html }), /unavailable/); assert.equal(failed.get().destroyed, true);
});
test('store receipt rejects missing or oversized input before creating a print window', async () => {
 const fake = fakeWindow();
 await assert.rejects(printReceipt(fake.Window, { html: '<script>wrong</script>' }), /Invalid/);
 await assert.rejects(printReceipt(fake.Window, { html: html + 'x'.repeat(1024 * 1024) }), /Invalid/);
 assert.equal(fake.get(), undefined);
});
