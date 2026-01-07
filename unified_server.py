"""
Unified Server for Krishna Voice Assistant
Combines HTTP (static files) + WebSocket on single port for cloud deployment
"""

import asyncio
import os
import json
import mimetypes
from pathlib import Path

# Fix for Windows event loop
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import websockets
from websockets.server import serve as websocket_serve

# Import the streaming orchestrator
from streaming_server import StreamingOrchestrator

# Get port from environment (Render sets this)
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

# Static file directory
STATIC_DIR = Path(__file__).parent


class UnifiedServer:
    """Serves both static files and WebSocket on same port"""
    
    def __init__(self):
        self.orchestrator = StreamingOrchestrator()
        
        # MIME types
        mimetypes.init()
        self.mime_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
        }
    
    def get_mime_type(self, path: str) -> str:
        """Get MIME type for file"""
        ext = Path(path).suffix.lower()
        return self.mime_types.get(ext, 'application/octet-stream')
    
    async def serve_static(self, path: str) -> tuple:
        """Serve static file, returns (status, headers, body)"""
        # Default to index
        if path == "/" or path == "":
            path = "/krishna_complete.html"
        
        # Security: prevent path traversal
        file_path = STATIC_DIR / path.lstrip("/")
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                return (403, [], b"Forbidden")
        except:
            return (403, [], b"Forbidden")
        
        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            # Try with .html extension
            html_path = STATIC_DIR / (path.lstrip("/") + ".html")
            if html_path.exists():
                file_path = html_path
            else:
                return (404, [], b"Not Found")
        
        # Read and serve file
        try:
            content = file_path.read_bytes()
            mime_type = self.get_mime_type(str(file_path))
            headers = [
                ("Content-Type", mime_type),
                ("Content-Length", str(len(content))),
                ("Access-Control-Allow-Origin", "*"),
            ]
            return (200, headers, content)
        except Exception as e:
            print(f"Error serving {file_path}: {e}")
            return (500, [], b"Internal Server Error")
    
    async def handle_connection(self, websocket):
        """Handle incoming connection - route to HTTP or WebSocket"""
        try:
            # Check if this is a WebSocket upgrade request
            path = websocket.request.path if hasattr(websocket, 'request') else "/"
            
            # Health check endpoint
            if path == "/health":
                await websocket.send(json.dumps({"status": "healthy", "service": "krishna-voice"}))
                return
            
            # WebSocket paths
            if path in ["/ws", "/websocket", "/"]:
                print(f"🔌 WebSocket connection from {websocket.remote_address}")
                await self.orchestrator.handle_client(websocket)
            else:
                # For non-WebSocket requests, we can't serve HTTP directly
                # The websockets library expects WebSocket connections
                print(f"📁 Static request for {path} - redirecting to root")
                
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")
        except Exception as e:
            print(f"Error handling connection: {e}")


async def http_handler(path, request_headers):
    """HTTP request handler for static files"""
    # Health check
    if path == "/health":
        return (200, [("Content-Type", "application/json")], b'{"status":"healthy"}')
    
    # Serve static files
    server = UnifiedServer()
    return await server.serve_static(path)


async def main():
    """Start the unified server"""
    server = UnifiedServer()
    
    print("=" * 60)
    print("🙏 KRISHNA VOICE ASSISTANT - CLOUD DEPLOYMENT")
    print("=" * 60)
    print(f"🌐 Server starting on http://{HOST}:{PORT}")
    print(f"🔌 WebSocket endpoint: ws://{HOST}:{PORT}/ws")
    print("=" * 60)
    
    # Start WebSocket server with HTTP fallback
    async with websocket_serve(
        server.handle_connection,
        HOST,
        PORT,
        process_request=http_handler,
        ping_interval=30,
        ping_timeout=10,
    ):
        print(f"✅ Server ready on port {PORT}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()
