import json
import sqlite3
import threading
import unittest
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from fiscal_bridge import Handler


class TestLocalFiscalBridge(unittest.TestCase):
    def setUp(self):
        self.calls = 0
        outer = self
        class Printer(BaseHTTPRequestHandler):
            def log_message(self, *_args): pass
            def do_POST(self):
                outer.calls += 1
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.payload = payload
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'rc':'SUCCESS','data':{'fdNumber':42,'fpd':'123'}}).encode())
        self.printer = HTTPServer(('127.0.0.1', 0), Printer)
        self.bridge = HTTPServer(('127.0.0.1', 0), Handler)
        self.bridge.printer = f'http://127.0.0.1:{self.printer.server_port}'
        self.bridge.origins = {'http://radolfa.localhost:8000'}
        self.bridge.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.bridge.db.execute('CREATE TABLE attempts (id TEXT PRIMARY KEY, result TEXT)')
        for server in (self.printer, self.bridge):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def tearDown(self):
        for server in (self.bridge, self.printer): server.shutdown(); server.server_close()
        self.bridge.db.close()

    def request(self, attempt, origin='http://radolfa.localhost:8000'):
        body = {'endpoint':'formReceipt','attempt':attempt,'payload':{'receiptSum':1234,'products':[{'sum':1234}]}}
        request = urllib.request.Request(f'http://127.0.0.1:{self.bridge.server_port}/fiscal/request',
            data=json.dumps(body).encode(),headers={'Origin':origin,'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response: return json.load(response)

    def test_canonical_tiyins_are_forwarded_once_and_result_is_replayed(self):
        one = self.request('a'*32); two = self.request('a'*32)
        self.assertEqual(one, two); self.assertEqual(self.calls, 1)
        self.assertEqual(self.payload['receiptSum'], 1234)

    def test_unknown_attempt_is_never_retransmitted(self):
        self.bridge.db.execute('INSERT INTO attempts(id) VALUES (?)', ('b'*32,)); self.bridge.db.commit()
        with self.assertRaises(urllib.error.HTTPError): self.request('b'*32)
        self.assertEqual(self.calls, 0)

    def test_untrusted_web_origin_cannot_reach_the_printer(self):
        with self.assertRaises(urllib.error.HTTPError) as exc: self.request('c'*32, 'https://example.com')
        self.assertEqual(exc.exception.code, 403); self.assertEqual(self.calls, 0)

    def test_shift_opening_is_forwarded_without_preparing_a_receipt(self):
        payload={'formCode':'OPEN_SHIFT','cashier':'Моҳира','shouldPrintSlip':True}
        request=urllib.request.Request(f'http://127.0.0.1:{self.bridge.server_port}/fiscal/request',
            data=json.dumps({'endpoint':'openShift','payload':payload}).encode(),
            headers={'Origin':'http://radolfa.localhost:8000','Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response: self.assertEqual(json.load(response)['rc'],'SUCCESS')
        self.assertEqual(self.payload,payload)
        self.assertEqual(self.bridge.db.execute('SELECT count(*) FROM attempts').fetchone()[0],0)


if __name__ == '__main__': unittest.main()
