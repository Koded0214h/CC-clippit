"""Dev server that always serves this frontend directory without caching."""
import functools
import http.server
import socketserver
from pathlib import Path

class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

socketserver.TCPServer.allow_reuse_address = True
handler = functools.partial(NoCache, directory=str(Path(__file__).resolve().parent))
with socketserver.TCPServer(("127.0.0.1", 5174), handler) as httpd:
    print("serving on http://localhost:5174/")
    httpd.serve_forever()
