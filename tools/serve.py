"""Static server for the render harness; POST /save/<name>.png stores a rendered image."""
import sys, os, re
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
ROOT, SHOTS, PORT = sys.argv[1], sys.argv[2], int(sys.argv[3])

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_POST(self):
        m = re.fullmatch(r'/save/([A-Za-z0-9_\-]+\.(?:png|jpg|webp))', self.path)
        if not m: self.send_error(400); return
        data = self.rfile.read(int(self.headers['Content-Length']))
        open(os.path.join(SHOTS, m.group(1)), 'wb').write(data)
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a): pass

ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
