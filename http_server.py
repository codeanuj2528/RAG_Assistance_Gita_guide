"""
Simple HTTP Server to serve the client HTML
"""

import http.server
import socketserver
import os
import threading

PORT = 8000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def start_http_server():
    """Start HTTP server to serve client files"""
    # Change to voice_ass directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Allow reusing the address (prevents WinError 10048)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print(f"📡 HTTP Server running at http://localhost:{PORT}")
        print(f"🌐 Open http://localhost:{PORT}/client.html in your browser")
        print("="*60)
        httpd.serve_forever()

if __name__ == "__main__":
    start_http_server()
