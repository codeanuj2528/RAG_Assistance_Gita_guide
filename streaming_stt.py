"""
Streaming Speech-to-Text with Partial Results
Target: <400ms latency for first partial
"""

import asyncio
import io
import time
import wave
from typing import Optional
from openai import AsyncOpenAI
from config import Config


class OpenAIStreamingSTT:
    """Streaming STT with partial and final transcripts (using OpenAI)"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.last_partial = ""
    
    def _wrap_wav(self, pcm_bytes: bytes) -> bytes:
        """Wrap raw PCM bytes in a WAV header"""
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(Config.CHANNELS)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(Config.SAMPLE_RATE)
                wav_file.writeframes(pcm_bytes)
            return wav_io.getvalue()

    async def transcribe_partial(self, audio_bytes: bytes) -> Optional[str]:
        """Get partial transcript from audio chunk"""
        try:
            # Wrap in WAV header
            wav_data = self._wrap_wav(audio_bytes)
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"
            
            start = time.time()
            response = await self.client.audio.transcriptions.create(
                model=Config.WHISPER_MODEL,
                file=audio_file,
                # Force language to Hindi to prevent detecting other scripts
                language="hi",
                # Context-rich prompt biased towards Krishna/Gita
                prompt="Lord Krishna, Bhagavad Gita, Dharma, Yoga, Partha. Hindi and English conversation only.",
                response_format="text"
            )
            
            elapsed = (time.time() - start) * 1000
            text = response.strip() if isinstance(response, str) else response.text.strip()
            
            if text and text != self.last_partial:
                print(f"⚡ STT partial ({elapsed:.0f}ms): {text}")
                self.last_partial = text
                return text
            
            return None
        except Exception as e:
            print(f"❌ STT partial error: {e}")
            return None
    
    async def transcribe_final(self, audio_bytes: bytes) -> Optional[str]:
        """Get final transcript from complete audio"""
        try:
            wav_data = self._wrap_wav(audio_bytes)
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"
            
            start = time.time()
            response = await self.client.audio.transcriptions.create(
                model=Config.WHISPER_MODEL,
                file=audio_file,
                response_format="verbose_json",
                temperature=0.0,
                language="hi",
                prompt="Hindi, English, Hinglish, Bhagavad Gita, Krishna, Dharma"
            )
            
            elapsed = (time.time() - start) * 1000
            text = response.text.strip()
            print(f"✅ STT final ({elapsed:.0f}ms): {text}")
            self.last_partial = ""
            return text
        except Exception as e:
            print(f"❌ STT final error: {e}")
            return None
    
    def reset(self):
        self.last_partial = ""


class GroqStreamingSTT:
    """Groq Whisper - typically faster than OpenAI"""
    
    def __init__(self):
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=Config.GROQ_API_KEY)
        self.last_partial = ""
    
    def _wrap_wav(self, pcm_bytes: bytes) -> bytes:
        """Wrap raw PCM bytes in a WAV header"""
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(Config.CHANNELS)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(Config.SAMPLE_RATE)
                wav_file.writeframes(pcm_bytes)
            return wav_io.getvalue()

    async def transcribe_partial(self, audio_bytes: bytes) -> Optional[str]:
        """Get partial transcript using Groq Whisper (Optimized window)"""
        try:
            # ONLY SEND LAST 3 SECONDS FOR PARTIALS TO REDUCE LATENCY
            # 16000 samples/sec * 2 bytes/sample = 32000 bytes/sec
            window_size = 32000 * 3 
            audio_window = audio_bytes[-window_size:] if len(audio_bytes) > window_size else audio_bytes

            wav_data = self._wrap_wav(audio_window)
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"
            
            start = time.time()
            print(f"📡 Groq STT partial starting (Window: {len(audio_window)} bytes)...")
            
            # Using asyncio.wait_for for robust timeout
            response = await asyncio.wait_for(
                self.client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("audio.wav", audio_file),
                    response_format="text",
                    prompt="Hindi, Hinglish, English conversation. User is speaking in Hindi or English."
                ),
                timeout=4.0  # Reduced for faster partials
            )
            
            elapsed = (time.time() - start) * 1000
            text = response.strip()
            
            if text and text != self.last_partial:
                print(f"⚡ Groq STT partial ({elapsed:.0f}ms): {text}")
                self.last_partial = text
                return text
            
            return None
        except asyncio.TimeoutError:
            print(f"❌ Groq STT partial timeout (>5s)")
            raise
        except Exception as e:
            print(f"❌ Groq STT partial error ({type(e).__name__}): {e}")
            raise
    
    async def transcribe_final(self, audio_bytes: bytes) -> Optional[str]:
        """Get final transcript using Groq Whisper"""
        try:
            wav_data = self._wrap_wav(audio_bytes)
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"
            
            start = time.time()
            print(f"📡 Groq STT final starting ({len(audio_bytes)} bytes)...")
            
            response = await asyncio.wait_for(
                self.client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("audio.wav", audio_file),
                    response_format="json",
                    temperature=0.0,
                    prompt="Hindi, Hinglish, English conversation. Transcribe speech in Hindi or English only."
                ),
                timeout=7.0  # Reduced for faster final fallback
            )
            
            elapsed = (time.time() - start) * 1000
            
            # Handle JSON response format
            if isinstance(response, str):
                text = response.strip()
            elif hasattr(response, 'text'):
                text = response.text.strip()
            else:
                # Groq's SDK might return a dict-like object for json format
                text = getattr(response, 'text', str(response)).strip()
                if isinstance(response, dict):
                    text = response.get('text', '')

            print(f"✅ Groq STT final ({elapsed:.0f}ms): {text}")
            
            # HALLUCINATION FILTER: Ignore common Whisper artifacts
            hallucinations = {
                "Obrigado.", "Pronto.", "Arigato.", "Thanks for watching!", 
                "Subtitles by", "Hindi", "English", "Please subscribe", 
                "unintelligible", "inaudible", "Thank you.", "Bye.", "Hey."
            }
            if text in hallucinations or len(text.strip()) < 2:
                print(f"⚠️ Ignored potential STT hallucination/junk: '{text}'")
                return None

            self.last_partial = ""
            return text
        except asyncio.TimeoutError:
            print(f"❌ Groq STT final timeout (>7s)")
            raise
        except Exception as e:
            print(f"❌ Groq STT final error ({type(e).__name__}): {e}")
            raise
    
    def reset(self):
        self.last_partial = ""


class FallbackStreamingSTT:
    """Tries Groq first, falls back to OpenAI if it fails or times out"""
    
    def __init__(self):
        self.groq = GroqStreamingSTT() if Config.GROQ_API_KEY else None
        self.openai = OpenAIStreamingSTT() if Config.OPENAI_API_KEY else None
        self.consecutive_groq_failures = 0
        self.last_partial = ""

    async def transcribe_partial(self, audio_bytes: bytes) -> Optional[str]:
        # If Groq is failing repeatedly, skip it for a bit
        if self.groq and self.consecutive_groq_failures < 3:
            try:
                text = await self.groq.transcribe_partial(audio_bytes)
                self.consecutive_groq_failures = 0 # Reset on success
                return text
            except Exception as e:
                print(f"⚠️ Groq partial failed, switching to OpenAI: {e}")
                self.consecutive_groq_failures += 1
        
        if self.openai:
            return await self.openai.transcribe_partial(audio_bytes)
        return None

    async def transcribe_final(self, audio_bytes: bytes) -> Optional[str]:
        # Always try Groq first but with a tight timeout (already in GroqStreamingSTT)
        if self.groq:
            try:
                text = await self.groq.transcribe_final(audio_bytes)
                if text:
                    self.consecutive_groq_failures = 0
                    return text
            except Exception as e:
                print(f"⚠️ Groq final failed/timed out, falling back to OpenAI: {e}")
                self.consecutive_groq_failures += 1

        if self.openai:
            print("📡 Trying OpenAI Whisper (Fallback)...")
            return await self.openai.transcribe_final(audio_bytes)
        
        return None

    def reset(self):
        if self.groq: self.groq.reset()
        if self.openai: self.openai.reset()
        self.consecutive_groq_failures = 0


# Default to the robust fallback version
StreamingSTT = FallbackStreamingSTT
print("✅ Using Fallback-Enabled STT (Groq -> OpenAI)")
