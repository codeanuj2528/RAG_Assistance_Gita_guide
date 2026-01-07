# 🕉️ Krishna Voice Assistant

> **Real-Time AI Voice Assistant powered by Bhagavad Gita Wisdom**

A low-latency (<1 second) voice assistant that speaks as Lord Krishna, providing spiritual guidance and life advice rooted in the Bhagavad Gita. Features real-time speech-to-text, AI-powered responses with RAG (Retrieval Augmented Generation), and natural text-to-speech.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![WebSocket](https://img.shields.io/badge/WebSocket-Real--Time-orange.svg)

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [How It Works](#-how-it-works)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Usage](#-usage)
- [Deployment](#-deployment)
- [Known Issues](#-known-issues)
- [Contributing](#-contributing)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎤 **Real-Time Voice Input** | WebSocket-based streaming audio capture at 16kHz |
| ⚡ **<1s Latency** | Optimized pipeline for sub-second response time |
| 🧠 **RAG-Powered Wisdom** | Retrieves relevant Gita verses for contextual answers |
| 🗣️ **Natural TTS** | ElevenLabs/OpenAI voice synthesis |
| 🎯 **Intent Classification** | Categorizes queries (Career, Relationships, Inner Conflict, etc.) |
| 🔄 **Barge-In Support** | Interrupt Krishna while speaking |
| 📊 **Live Metrics** | Real-time latency tracking dashboard |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                          │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────────┐  │
│  │   Mic   │───▶│ Resample │───▶│  WS     │───▶│  Speaker    │  │
│  │ Capture │    │ (16kHz)  │    │ Client  │◀───│  Playback   │  │
│  └─────────┘    └──────────┘    └────┬────┘    └─────────────┘  │
└──────────────────────────────────────│──────────────────────────┘
                                       │ WebSocket
┌──────────────────────────────────────▼──────────────────────────┐
│                     SERVER (Python Asyncio)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              StreamingOrchestrator                        │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │   │
│  │  │   STT   │─▶│   RAG   │─▶│   LLM   │─▶│    TTS      │  │   │
│  │  │ Whisper │  │ChromaDB │  │ Groq/   │  │ ElevenLabs/ │  │   │
│  │  │         │  │         │  │ OpenAI  │  │   OpenAI    │  │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 How It Works

### 1. Voice Capture
- Browser captures audio via Web Audio API
- Resampled to 16kHz mono PCM
- Streamed via WebSocket in 40ms chunks

### 2. Speech-to-Text (STT)
- **Primary**: Groq Whisper Large v3 (fastest)
- **Fallback**: OpenAI Whisper
- Supports Hindi, English, and Hinglish

### 3. RAG Pipeline
- User query embedded using `sentence-transformers/all-MiniLM-L6-v2`
- ChromaDB searches 700+ Gita verses
- Top 3 relevant verses retrieved for context

### 4. Intent Classification
- Categorizes query into: Career/Purpose, Relationships, Inner Conflict, Life Transitions, Daily Struggles
- Guides LLM to provide focused wisdom

### 5. LLM Response
- **Primary**: Groq LLaMA-3.3-70B (instant)
- **Fallback**: OpenAI GPT-4o-mini
- Token-by-token streaming for low latency

### 6. Text-to-Speech (TTS)
- **Primary**: ElevenLabs (deep, Krishna-like voice)
- **Fallback**: OpenAI TTS
- Sentence-by-sentence streaming for fast response

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.11+, asyncio, websockets |
| **STT** | OpenAI Whisper, Groq Whisper |
| **LLM** | Groq LLaMA-3.3-70B, OpenAI GPT-4o-mini |
| **TTS** | ElevenLabs, OpenAI TTS |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) |
| **Vector DB** | ChromaDB |
| **Frontend** | Vanilla HTML/JS, Web Audio API |
| **Deployment** | Docker, Render.com |

---

## 📁 Project Structure

```
Krishna_Voice/
├── 📄 unified_server.py      # Main cloud deployment server
├── 📄 streaming_server.py    # WebSocket orchestrator
├── 📄 streaming_stt.py       # Speech-to-Text (Whisper)
├── 📄 streaming_llm.py       # LLM responses (Groq/OpenAI)
├── 📄 streaming_tts.py       # Text-to-Speech (ElevenLabs)
├── 📄 rag_embedder.py        # Build vector embeddings
├── 📄 rag_retriever.py       # Retrieve relevant verses
├── 📄 intent_classifier.py   # Query intent classification
├── 📄 response_evaluator.py  # Response quality metrics
├── 📄 config.py              # Configuration & API keys
├── 📄 krishna_complete.html  # Web UI (single file)
├── 📄 requirements.txt       # Python dependencies
├── 📄 Dockerfile             # Container configuration
├── 📄 render.yaml            # Render.com deployment
└── 📁 data/                  # Bhagavad Gita data
    ├── verse.json            # 700+ Sanskrit verses
    ├── translation.json      # English translations
    ├── commentary.json       # Scholarly commentaries
    └── chapters.json         # Chapter summaries
```

---

## 🚀 Installation

### Prerequisites
- Python 3.11+
- API Keys: OpenAI, Groq, ElevenLabs (optional)

### Local Setup

```bash
# Clone repository
git clone https://github.com/codeanuj2528/RAG_Assistance_Gita_guide.git
cd RAG_Assistance_Gita_guide

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo OPENAI_API_KEY=your-key > .env
echo GROQ_API_KEY=your-key >> .env
echo ELEVENLABS_API_KEY=your-key >> .env

# Build RAG embeddings (first time only)
python rag_embedder.py

# Start server
python streaming_server.py
```

### Access
Open `krishna_complete.html` in browser, or visit `http://localhost:8765`

---

## 💬 Usage

1. **Click "START RECORDING"** - Microphone activates
2. **Speak your question** - e.g., "I'm confused about my career"
3. **Wait for Krishna's response** - Audio plays automatically
4. **Click again to ask another question**

### Example Questions
- "What should I do when I feel lost in life?"
- "How do I handle stress at work?"
- "I'm having relationship problems, what does the Gita say?"
- "मुझे अपने भविष्य की चिंता है" (Hindi supported)

---

## ☁️ Deployment

### Render.com (FREE)

1. **Fork/Push to GitHub**

2. **Go to [render.com](https://render.com)** → Sign up with GitHub

3. **Create Web Service**:
   - Repository: `codeanuj2528/RAG_Assistance_Gita_guide`
   - Runtime: Docker
   - Instance: Free

4. **Add Environment Variables**:
   ```
   OPENAI_API_KEY=sk-...
   GROQ_API_KEY=gsk_...
   ELEVENLABS_API_KEY=... (optional)
   ```

5. **Deploy** → Get live URL: `https://your-app.onrender.com`

### Docker (Self-hosted)

```bash
docker build -t krishna-voice .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=your-key \
  -e GROQ_API_KEY=your-key \
  krishna-voice
```

---

## ⚠️ Known Issues

| Issue | Status | Workaround |
|-------|--------|------------|
| First request slow on Render free tier | Expected | Service wakes from sleep in ~30s |
| Groq rate limits during heavy use | Handled | Auto-fallback to OpenAI |
| Hindi TTS pronunciation | Partial | ElevenLabs handles better than OpenAI |
| WebSocket disconnect on network change | Known | Refresh page to reconnect |
| ChromaDB not persisted on Render | Design | Rebuilds on each deploy (~30s) |

---

## 📊 Performance Metrics

| Metric | Target | Achieved |
|--------|--------|----------|
| STT Latency | <500ms | ~300-400ms |
| LLM First Token | <300ms | ~150-250ms |
| TTS First Audio | <500ms | ~400-600ms |
| **Total Handoff** | **<1500ms** | **800-1200ms** ✅ |

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **Bhagavad Gita data** from [Bhagavad Gita API](https://bhagavadgitaapi.in/)
- **ElevenLabs** for realistic voice synthesis
- **Groq** for lightning-fast LLM inference
- **OpenAI** for Whisper STT and fallback services

---

<div align="center">

**Built with ❤️ and devotion**

*"You have the right to work, but never to the fruit of work." - Bhagavad Gita 2.47*

</div>
