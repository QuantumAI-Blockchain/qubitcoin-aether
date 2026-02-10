#!/usr/bin/env python3
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

class DebugHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            print("\n=== Fetching data from API ===")
            response = requests.get("http://localhost:5000/info", timeout=2)
            print(f"Status: {response.status_code}")
            
            data = response.json()
            print(f"Data received: {data}")
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>API is working!</h1>")
            
        except Exception as e:
            print(f"\n=== ERROR ===")
            print(f"Error: {e}")
            traceback.print_exc()
            
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            error_html = f"<h1>Error: {e}</h1><pre>{traceback.format_exc()}</pre>"
            self.wfile.write(error_html.encode())

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8090), DebugHandler)
    print("Debug server running on http://0.0.0.0:8090")
    server.serve_forever()
