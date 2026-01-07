"""
Launch Script for Krishna Real-Time Voice Assistant
Starts both WebSocket server and HTTP server
"""

import asyncio
import subprocess
import sys
import os
from threading import Thread

def start_http_server():
    """Start HTTP server in separate process"""
    print("🌐 Starting HTTP server...")
    subprocess.run([sys.executable, "http_server.py"])

def start_websocket_server():
    """Start WebSocket server"""
    print("🚀 Starting WebSocket server...")
    subprocess.run([sys.executable, "streaming_server.py"])

def main():
    """Launch both servers"""
    print("="*60)
    print("🕉️  KRISHNA REAL-TIME VOICE ASSISTANT")
    print("="*60)
    print("⚡ Target Latency: <1 second")
    print("🎯 Architecture: Parallel Streaming Pipeline")
    print("="*60)
    print()
    
    # Check if .env exists
    if not os.path.exists('.env'):
        print("⚠️  WARNING: .env file not found!")
        print("Please create a .env file with your API keys:")
        print()
        print("OPENAI_API_KEY=your_key_here")
        print("GROQ_API_KEY=your_key_here  # Optional but recommended for speed")
        print("ELEVENLABS_API_KEY=your_key_here  # Optional for better TTS")
        print()
        return
    
    try:
        # Validate config
        from config import Config
        Config.validate()
        
        print("✅ Configuration validated")
        print()
        
        # Start HTTP server in background thread
        http_thread = Thread(target=start_http_server, daemon=True)
        http_thread.start()
        
        # Give HTTP server time to start
        import time
        time.sleep(2)
        
        print()
        print("="*60)
        print("🎉 SERVERS READY!")
        print("="*60)
        print("📡 WebSocket: ws://localhost:8765")
        print("🌐 Web Client: http://localhost:8000/krishna_complete.html")
        print("="*60)
        print()
        print("👉 Open http://localhost:8000/krishna_complete.html in your browser")
        print("👉 Select your microphone and click START RECORDING")
        print()
        print("Press Ctrl+C to stop")
        print("="*60)
        print()
        
        # Start WebSocket server (blocking)
        start_websocket_server()
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down servers...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
