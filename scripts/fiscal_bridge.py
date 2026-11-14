#!/usr/bin/env python3
"""Local browser TP809 bridge. Start with --origin https://your-pos-site.

Uses only Python's standard library. Retains transmission results in SQLite so
recovery after a lost ERP response cannot issue a second fiscal document.
"""
import argparse
import json
import sqlite3
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def headers_for(self, status):
        self.send_response(status)
        if self.headers.get("Origin") in self.server.origins:
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_OPTIONS(self):
        self.headers_for(204 if self.headers.get("Origin") in self.server.origins else 403)

    def do_POST(self):
        if self.headers.get("Origin") not in self.server.origins or self.path != "/fiscal/request":
            self.headers_for(403)
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 1024 * 1024:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(size))
            endpoint = request.get("endpoint")
            if endpoint not in {"formReceipt", "getFDByNumber", "deviceStatus", "openShift", "closeShift"}:
                raise ValueError("Unsupported fiscal operation")
            attempt = request.get("attempt")
            if endpoint == "formReceipt":
                if not isinstance(attempt, str) or not attempt.isalnum() or not 16 <= len(attempt) <= 64:
                    raise ValueError("Prepared fiscal attempt required")
                row = self.server.db.execute("SELECT result FROM attempts WHERE id=?", (attempt,)).fetchone()
                if row:
                    if not row[0]:
                        raise ValueError("Fiscal result unknown. Reconcile the printer journal.")
                    self.headers_for(200)
                    self.wfile.write(row[0].encode())
                    return
                self.server.db.execute("INSERT INTO attempts(id) VALUES (?)", (attempt,))
                self.server.db.commit()
            req = urllib.request.Request(self.server.printer + "/api/" + endpoint,
                data=json.dumps(request["payload"], ensure_ascii=False).encode(),
                headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
            # No redirects: only the operator-configured physical device is contacted.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *_args, **_kwargs):
                    return None
            with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as response:
                result = json.loads(response.read(1024 * 1024).decode())
            serialized = json.dumps(result)
            if endpoint == "formReceipt":
                self.server.db.execute("UPDATE attempts SET result=? WHERE id=?", (serialized, attempt))
                self.server.db.commit()
            self.headers_for(200)
            self.wfile.write(serialized.encode())
        except Exception as exc:
            self.headers_for(502)
            self.wfile.write(json.dumps({"error": str(exc)}).encode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--printer", required=True)
    parser.add_argument("--origin", required=True, action="append")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--journal", default="fiscal-attempts.sqlite3")
    args = parser.parse_args()
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.printer = args.printer.rstrip("/")
    server.origins = set(args.origin)
    server.db = sqlite3.connect(args.journal)
    server.db.execute("CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, result TEXT)")
    server.db.commit()
    server.serve_forever()
