const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { fiscalRequest, printerUrl } = require('../electron/fiscal');

test('desktop refuses public URLs, credentials and arbitrary endpoints', () => {
 for (const url of ['https://example.com', 'http://admin:secret@127.0.0.1', 'file:///tmp/x']) assert.throws(() => printerUrl(url, 'formReceipt'));
 assert.throws(() => printerUrl('http://127.0.0.1:8002', 'arbitrary'));
 assert.equal(printerUrl('http://192.168.1.2:8002', 'formReceipt').pathname, '/api/formReceipt');
});

test('desktop journal replays a response without another fiscal transmission', async () => {
 let calls = 0;
 const server = http.createServer((_req, res) => { calls++; res.end(JSON.stringify({ rc: 'SUCCESS', data: { fdNumber: 1, fpd: '123' } })); });
 await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
 try {
  const data = new Map(); const store = { get: k => data.get(k), set: (k, v) => data.set(k, v) };
  const request = { printer_url: `http://127.0.0.1:${server.address().port}`, endpoint: 'formReceipt', attempt: 'a'.repeat(32), payload: { receiptSum: 1000 } };
  const one = await fiscalRequest(store, request); const two = await fiscalRequest(store, request);
  assert.deepEqual(one, two); assert.equal(calls, 1);
 } finally { server.close(); }
});

test('desktop never resends an attempt whose result is unknown', async () => {
 const store = { get: () => ({ state: 'unknown' }), set: () => assert.fail('must not mutate prior attempt') };
 await assert.rejects(fiscalRequest(store, { printer_url: 'http://127.0.0.1:8002', endpoint: 'formReceipt', attempt: 'b'.repeat(32), payload: {} }), /unknown/);
});

test('desktop allows the verified fiscal shift opening operation', async () => {
 let received;
 const server = http.createServer((req, res) => { let body=''; req.on('data', b => body+=b); req.on('end',()=>{received={path:req.url,payload:JSON.parse(body)};res.end(JSON.stringify({rc:'SUCCESS',data:{shiftNumber:419}}));}); });
 await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
 try {
  const result=await fiscalRequest({get:()=>null,set:()=>assert.fail('opening must not prepare a sale')},{printer_url:`http://127.0.0.1:${server.address().port}`,endpoint:'openShift',payload:{formCode:'OPEN_SHIFT',cashier:'Моҳира',shouldPrintSlip:true}});
  assert.equal(result.data.shiftNumber,419);assert.equal(received.path,'/api/openShift');assert.equal(received.payload.cashier,'Моҳира');
 } finally {server.close();}
});
