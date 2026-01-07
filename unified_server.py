"""
Unified Server for Krishna Voice Assistant
Combines HTTP (static files) + WebSocket on single port for cloud deployment

Fixed for Render.com deployment with proper WebSocket handling.
"""

import asyncio
import os
import json
import mimetypes
from pathlib import Path
from http import HTTPStatus

# Fix for Windows event loop
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import websockets
from websockets.server import serve

# Get port from environment (Render sets this)
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

# Static file directory
STATIC_DIR = Path(__file__).parent

# Global orchestrator instance (singleton)
_orchestrator = None

def get_orchestrator():
    """Get or create global orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        from streaming_server import StreamingOrchestrator
        _orchestrator = StreamingOrchestrator()
    return _orchestrator


# MIME types mapping
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
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


def get_mime_type(path: str) -> str:
    """Get MIME type for file"""
    ext = Path(path).suffix.lower()
    return MIME_TYPES.get(ext, 'application/octet-stream')


async def serve_static_file(path: str):
    """Serve static file, returns (status, headers, body)"""
    # Default to index
    if path == "/" or path == "":
        path = "/krishna_complete.html"
    
    # Security: prevent path traversal
    file_path = STATIC_DIR / path.lstrip("/")
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())):
            return (HTTPStatus.FORBIDDEN, [], b"Forbidden")
    except:
        return (HTTPStatus.FORBIDDEN, [], b"Forbidden")
    
    # Check if file exists
    if not file_path.exists() or not file_path.is_file():
        return (HTTPStatus.NOT_FOUND, [], b"Not Found")
    
    # Read and serve file
    try:
        content = file_path.read_bytes()
        mime_type = get_mime_type(str(file_path))
        headers = [
            ("Content-Type", mime_type),
            ("Content-Length", str(len(content))),
            ("Access-Control-Allow-Origin", "*"),
            ("Cache-Control", "no-cache"),
        ]
        return (HTTPStatus.OK, headers, content)
    except Exception as e:
        print(f"Error serving {file_path}: {e}")
        return (HTTPStatus.INTERNAL_SERVER_ERROR, [], b"Internal Server Error")


async def process_request(path, request_headers):
    """
    Process incoming HTTP requests.
    
    Returns:
        - None: Allow WebSocket upgrade (for /ws endpoint)
        - Tuple: Return HTTP response (for static files)
    """
    print(f"📨 Request: {path}")
    
    # Health check endpoint
    if path == "/health":
        body = b'{"status":"healthy","service":"krishna-voice"}'
        return (HTTPStatus.OK, [("Content-Type", "application/json")], body)
    
    # WebSocket paths - return None to allow upgrade
    if path in ["/ws", "/websocket"]:
        print(f"🔌 WebSocket upgrade request for {path}")
        return None  # Allow WebSocket upgrade
    
    # Serve static files for all other paths
    return await serve_static_file(path)


async def websocket_handler(websocket):
    """Handle WebSocket connections"""
    try:
        path = websocket.request.path if hasattr(websocket, 'request') else "/"
        print(f"🔌 WebSocket connected: {websocket.remote_address} path={path}")
        
        # Get the global orchestrator
        orchestrator = get_orchestrator()
        
        # Handle the WebSocket connection
        await orchestrator.handle_client(websocket)
        
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 WebSocket closed: {e}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Start the unified server"""
    print("=" * 60)
    print("🙏 KRISHNA VOICE ASSISTANT - CLOUD DEPLOYMENT")
    print("=" * 60)
    print(f"🌐 HTTP Server: http://{HOST}:{PORT}")
    print(f"🔌 WebSocket: wss://{HOST}:{PORT}/ws")
    print("=" * 60)
    
    # Pre-initialize orchestrator
    print("🔄 Initializing orchestrator...")
    orchestrator = get_orchestrator()
    print("✅ Orchestrator ready")
    
    # Start server
    async with serve(
        websocket_handler,
        HOST,
        PORT,
        process_request=process_request,
        ping_interval=30,
        ping_timeout=10,
        max_size=10 * 1024 * 1024,  # 10MB max message
    ):
        print(f"✅ Server ready on port {PORT}")
        print("🎧 Waiting for connections...")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        print("🚀 Starting Krishna Voice Server...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()
