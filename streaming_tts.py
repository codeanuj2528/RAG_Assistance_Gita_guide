"""
Streaming Text-to-Speech with Sentence-by-Sentence Generation
Target: First audio <500ms
"""

import asyncio
import io
import time
import json
import httpx
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from config import Config
from dotenv import load_dotenv
load_dotenv()


class StreamingTTS:
    """Streaming TTS with sentence-by-sentence audio generation"""
    
    def __init__(self):
        # Config is the authoritative source
        self.elevenlabs_api_key = Config.ELEVENLABS_API_KEY
        self.elevenlabs_voice_id = Config.ELEVENLABS_VOICE_ID
        self.use_elevenlabs = bool(self.elevenlabs_api_key)
        
        # Always initialize OpenAI as fallback if key exists
        if Config.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
            print("✅ OpenAI TTS initialized (as fallback)")
        
        if self.use_elevenlabs:
            print(f"✅ Using ElevenLabs TTS (REST API): {self.elevenlabs_voice_id}")
            self.provider = "ElevenLabs"
        elif hasattr(self, 'openai_client'):
            self.provider = "OpenAI"
            print("✅ Using OpenAI TTS")
        else:
            print("❌ No TTS API keys found! Please check your .env file.")
            self.provider = "None"
    
    async def stream_audio(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream audio chunks for given text
        Args:
            text: Text to convert to speech
        Yields:
            Audio chunks
        """
        if not text.strip():
            return
        
        if self.use_elevenlabs:
            async for chunk in self._stream_elevenlabs(text):
                yield chunk
        elif hasattr(self, 'openai_client'):
            async for chunk in self._stream_openai(text):
                yield chunk
    
    async def _stream_elevenlabs(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream audio using ElevenLabs REST API (Fastest & most robust)"""
        try:
            start = time.time()
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}/stream"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            data = {
                "text": text,
                "model_id": Config.ELEVENLABS_MODEL,
                "voice_settings": {
                    "stability": Config.ELEVENLABS_STABILITY,
                    "similarity_boost": Config.ELEVENLABS_SIMILARITY,
                    "style": Config.ELEVENLABS_STYLE,
                    "use_speaker_boost": Config.ELEVENLABS_SPEAKER_BOOST
                }
            }
            
            # Using 16kHz PCM for low latency and easy decoding
            params = {"output_format": "pcm_16000"}
            
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=data, headers=headers, params=params, timeout=30.0) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise Exception(f"ElevenLabs API Error {response.status_code}: {error_text.decode()}")
                    
                    first_chunk = True
                    chunk_count = 0
                    
                    async for chunk in response.aiter_bytes():
                        if first_chunk:
                            latency = (time.time() - start) * 1000
                            print(f"⚡ ElevenLabs (REST) first chunk: {latency:.0f}ms")
                            first_chunk = False
                        
                        chunk_count += 1
                        yield chunk
            
            total_time = (time.time() - start) * 1000
            print(f"✅ ElevenLabs (REST) complete: {chunk_count} chunks in {total_time:.0f}ms")
            
        except Exception as e:
            print(f"❌ ElevenLabs REST error: {e}")
            # If quota exceeded or unauthorized, stop trying for this session
            if "quota_exceeded" in str(e).lower() or "401" in str(e):
                print("⚠️ Switching to OpenAI TTS for the rest of this session...")
                self.use_elevenlabs = False
                
            if hasattr(self, 'openai_client'):
                async for chunk in self._stream_openai(text):
                    yield chunk
    
    async def _stream_openai(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream audio using OpenAI TTS (Low Latency)"""
        try:
            start = time.time()
            async with self.openai_client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=Config.OPENAI_VOICE,
                input=text,
                response_format="pcm",
                speed=1.0
            ) as response:
                first_chunk = True
                async for chunk in response.iter_bytes(chunk_size=4096):
                    if first_chunk:
                        latency = (time.time() - start) * 1000
                        print(f"⚡ OpenAI TTS first chunk: {latency:.0f}ms")
                        first_chunk = False
                    yield chunk
            
        except Exception as e:
            print(f"❌ OpenAI TTS error: {e}")
    
    async def generate_full_audio(self, text: str) -> Optional[bytes]:
        """Generate complete audio (non-streaming)"""
        try:
            if self.use_elevenlabs:
                def generate_audio():
                    # generate returns an iterator of bytes even if stream=False in some versions, 
                    # but usually it returns the full bytes if stream=False.
                    return self.elevenlabs_client.generate(
                        text=text,
                        voice=self.elevenlabs_voice_id,
                        model=Config.ELEVENLABS_MODEL,
                        stream=False,
                        output_format="pcm_16000",
                        voice_settings={
                            "stability": Config.ELEVENLABS_STABILITY,
                            "similarity_boost": Config.ELEVENLABS_SIMILARITY,
                            "style": Config.ELEVENLABS_STYLE,
                            "use_speaker_boost": Config.ELEVENLABS_SPEAKER_BOOST
                        }
                    )
                
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, generate_audio)
                if isinstance(result, bytes):
                    return result
                return b''.join(result) # Handle generator if returned
            elif hasattr(self, 'openai_client'):
                response = await self.openai_client.audio.speech.create(
                    model="tts-1",
                    voice=Config.OPENAI_VOICE,
                    input=text
                )
                return response.content
            return None
                
        except Exception as e:
            print(f"❌ TTS generation error: {e}")
            return None



class OptimizedStreamingTTS(StreamingTTS):
    """
    Optimized TTS with aggressive chunking and caching
    """
    
    def __init__(self):
        super().__init__()
        self.cache = {}  # Cache common phrases
    
    async def stream_audio(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream audio with optimizations:
        1. Check cache for common phrases
        2. Split long text into smaller chunks
        3. Generate and stream in parallel
        """
        text = text.strip()
        
        if not text:
            return
        
        # Check cache
        if text in self.cache:
            print(f"💾 Cache hit: {text[:30]}...")
            yield self.cache[text]
            return
        
        # For long text, split into smaller chunks
        if len(text) > 100:
            chunks = self._split_into_chunks(text)
            for chunk in chunks:
                async for audio in super().stream_audio(chunk):
                    yield audio
        else:
            # Generate normally
            audio_chunks = []
            async for chunk in super().stream_audio(text):
                audio_chunks.append(chunk)
                yield chunk
            
            # Cache if small enough
            if len(text) < 50:
                self.cache[text] = b''.join(audio_chunks)
    
    def _split_into_chunks(self, text: str) -> list:
        """Split text into speakable chunks"""
        # Split on sentence boundaries
        import re
        sentences = re.split(r'([.!?।]\s+)', text)
        
        chunks = []
        current = ""
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]
            
            if len(current) + len(sentence) < 100:
                current += sentence
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence
        
        if current:
            chunks.append(current.strip())
        
        return chunks


# Use optimized version
StreamingTTS = OptimizedStreamingTTS
