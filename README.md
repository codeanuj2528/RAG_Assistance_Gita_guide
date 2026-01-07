# Krishna Voice Assistant - Production Deployment

## Quick Start

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the server:
   ```
   python launch.py
   ```

3. Open in browser:
   ```
   http://localhost:8000/krishna_complete.html
   ```

## Features
- Real-time voice input/output
- RAG with 4907 Gita verses
- Response quality evaluation
- Hindi/English/Hinglish support

## Files
- launch.py - Main entry point
- krishna_complete.html - Web client
- streaming_server.py - WebSocket server
- rag_retriever.py - Verse retrieval
- response_evaluator.py - Quality scoring
