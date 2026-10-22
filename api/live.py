from http.server import BaseHTTPRequestHandler
from api._common import live_sources, send

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self): send(self, 204, {})
    def do_GET(self):
        send(self, 200, live_sources.snapshot())
