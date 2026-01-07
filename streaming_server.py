"""
Real-Time WebSocket Server for Krishna Voice Assistant
OPTIMIZED FOR <1 SECOND LATENCY

Architecture:
Mic -> WebSocket -> Streaming STT -> Streaming LLM -> Streaming TTS -> Speaker

Key Features:
- 20-40ms audio chunks
- Partial transcript processing
- Token-by-token LLM streaming
- Sentence-by-sentence TTS streaming
- Barge-in support (interruption)
"""

import asyncio
import json
import time
import io
import websockets
from typing import AsyncGenerator, Optional, Any
import numpy as np

# Import our optimized modules
from config import Config
from streaming_stt import StreamingSTT
from streaming_llm import StreamingLLM
from streaming_tts import StreamingTTS
from intent_classifier import IntentClassifier

# Response quality evaluation (optional)
try:
    from response_evaluator import get_evaluator
    EVALUATION_ENABLED = Config.ENABLE_EVALUATION if hasattr(Config, 'ENABLE_EVALUATION') else True
except ImportError:
    EVALUATION_ENABLED = False
    print("ℹ️ Response evaluation disabled (response_evaluator.py not found)")


class StreamingOrchestrator:
    """Orchestrates parallel streaming pipeline with <1s latency"""
    
    def __init__(self):
        self.stt = StreamingSTT()
        self.llm = StreamingLLM()
        self.tts = StreamingTTS()
        self.intent_classifier = IntentClassifier()
        
        # State management
        self.is_speaking = False
        self.should_interrupt = False
        self.conversation_history = []
        self.last_audio_chunk_at = time.time()
        self.current_turn_id = 0
        self.processed_turn_id = -1
        
        # NEW: Processing lock to prevent duplicate LLM/TTS cycles
        self.processing_lock = asyncio.Lock()
        self.is_processing = False
        
        # NEW: Track if final was already sent for current turn
        self._final_sent_for_turn = -1
        
        # Performance metrics
        self.metrics = {
            'audio_received_at': 0,
            'stt_first_partial_at': 0,
            'llm_first_token_at': 0,
            'tts_first_audio_at': 0,
            'user_heard_at': 0
        }
        
        # Track turn start time separately (not reset during processing)
        self._turn_start_time = 0
        self._chunk_count = 0
    
    async def handle_client(self, websocket: Any, *args):
        """Handle WebSocket connection from client"""
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"📡 CONNECTION ATTEMPT from {client_info}")
        print(f"✅ Client connected from {websocket.remote_address}")
        
        try:
            # Create tasks for parallel processing
            audio_buffer = asyncio.Queue()
            transcript_buffer = asyncio.Queue()
            llm_token_buffer = asyncio.Queue()
            
            # Start parallel pipeline with error handling
            print("🚀 Starting parallel pipeline tasks...")
            tasks = [
                asyncio.create_task(self.receive_audio(websocket, audio_buffer), name="receive_audio"),
                asyncio.create_task(self.monitor_silence(audio_buffer, websocket), name="monitor_silence"),
                asyncio.create_task(self.process_stt(audio_buffer, transcript_buffer, llm_token_buffer, websocket), name="process_stt"),
                asyncio.create_task(self.process_llm(transcript_buffer, llm_token_buffer, websocket), name="process_llm"),
                asyncio.create_task(self.process_tts(llm_token_buffer, websocket), name="process_tts")
            ]
            
            # Wait for any task to complete (usually means disconnect)
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            # Log which task completed/failed
            for task in done:
                task_name = task.get_name()
                if task.exception():
                    print(f"❌ Task '{task_name}' failed with error: {task.exception()}")
                    import traceback
                    traceback.print_exception(type(task.exception()), task.exception(), task.exception().__traceback__)
                else:
                    print(f"✅ Task '{task_name}' completed normally")
            
            # Cancel remaining tasks
            for task in pending:
                print(f"🛑 Cancelling task: {task.get_name()}")
                task.cancel()
                
        except websockets.exceptions.ConnectionClosed:
            print("❌ Client disconnected")
        except Exception as e:
            print(f"❌ Error in handle_client: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"🔌 Connection closed for {client_info}")
    
    async def receive_audio(self, websocket: Any, audio_buffer: asyncio.Queue):
        """Receive audio chunks from client (20-40ms chunks)"""
        print("🎤 Audio receiver started")
        
        message_count = 0
        audio_chunk_count = 0
        
        async for message in websocket:
            try:
                message_count += 1
                data = json.loads(message)
                
                # LOG EVERY MESSAGE TYPE
                msg_type = data.get('type', 'unknown')
                if msg_type == 'audio_chunk':
                    audio_chunk_count += 1
                    if audio_chunk_count % 10 == 0:
                        print(f"✅ Received audio chunk #{audio_chunk_count} (total messages: {message_count})")
                else:
                    print(f"📨 Received message type: {msg_type} (total messages: {message_count})")
                
                if data['type'] == 'audio_chunk':
                    # Only drop audio during TTS playback (feedback prevention)
                    if self.is_speaking:
                        # Allow audio chunks even while speaking for barge-in detection
                        # Feedback suppression should be handled on the client or via AEC
                        pass

                    # Start new turn if this is first audio
                    if self.metrics['audio_received_at'] == 0:
                        self._reset_metrics()
                        self.metrics['audio_received_at'] = time.time()
                        self._turn_start_time = time.time()
                        self.current_turn_id += 1
                        self._chunk_count = 0
                        print(f"🆕 New turn {self.current_turn_id} started")
                    
                    self._chunk_count += 1
                    if self._chunk_count % 20 == 0:
                        print(f"📥 Received {self._chunk_count} chunks from client (Last chunk at {time.time():.2f})")

                    self.last_audio_chunk_at = time.time()
                    
                    # Decode audio data (base64 encoded PCM)
                    import base64
                    import numpy as np
                    audio_bytes = base64.b64decode(data['audio'])
                    
                    # Calculate energy (RMS) to detect silence vs mic issues
                    try:
                        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
                        rms = np.sqrt(np.mean(audio_int16.astype(np.float64)**2))
                        if self._chunk_count % 10 == 0: # Log every 10th chunk to avoid spam
                            print(f"🔊 Audio RMS: {rms:.2f} (Max: {np.max(np.abs(audio_int16))})")
                    except Exception as e:
                        print(f"⚠️ Error calculating RMS: {e}")

                    # Put in buffer for STT processing
                    await audio_buffer.put(audio_bytes)
                    
                elif data['type'] == 'interrupt':
                    # User started speaking while AI was talking
                    print("⚠️ INTERRUPT - User barged in")
                    self.should_interrupt = True
                    self.is_speaking = False
                    
                    # Clear all buffers
                    while not audio_buffer.empty():
                        audio_buffer.get_nowait()
                    self._reset_metrics()
                    
                elif data['type'] == 'end_of_speech':
                    # User finished speaking manually
                    print(f"🛑 End of speech signal received (received {audio_chunk_count} audio chunks total)")
                    await audio_buffer.put(None)
                    
            except json.JSONDecodeError:
                print("❌ Invalid JSON received")
            except Exception as e:
                print(f"❌ Error receiving audio: {e}")

    async def monitor_silence(self, audio_buffer: asyncio.Queue, websocket: Any):
        """Monitor for silence and auto-trigger final transcription"""
        print("🔇 Silence monitor started")
        try:
            while True:
                await asyncio.sleep(0.2)
                # If no audio for 700ms (aggressive), trigger final
                # But ONLY if we haven't already sent final for this turn
                if (self.metrics['audio_received_at'] > 0 and 
                    not self.is_speaking and 
                    not self.is_processing and
                    self._final_sent_for_turn < self.current_turn_id):
                    
                    silence_duration = time.time() - self.last_audio_chunk_at
                    if silence_duration >= 0.7:
                        print(f"🔇 Silence detected ({silence_duration:.1f}s) - Auto-triggering final")
                        self._final_sent_for_turn = self.current_turn_id  # Mark as sent
                        self.metrics['audio_received_at'] = 0 
                        await audio_buffer.put(None)
        except Exception as e:
            print(f"🔇 Silence monitor stopped: {e}")
    
    async def process_stt(self, audio_buffer: asyncio.Queue, transcript_buffer: asyncio.Queue, llm_token_buffer: asyncio.Queue, websocket: Any):
        """Process streaming STT with partial results"""
        print("🎯 STT processor started")
        
        audio_chunks = []
        partial_task = None
        last_partial_trigger_at = 0
        
        while True:
            # Drain queue and add to chunks
            chunk = await audio_buffer.get()
            
            # If we get a real chunk, keep draining any pending chunks immediately
            if chunk is not None:
                audio_chunks.append(chunk)
                while not audio_buffer.empty():
                    next_chunk = audio_buffer.get_nowait()
                    if next_chunk is None:
                        chunk = None # Trigger final
                        break
                    audio_chunks.append(next_chunk)
            
            if chunk is None:
                # End of speech - cancel any pending partial to prioritize final
                if partial_task and not partial_task.done():
                    partial_task.cancel()
                    print("🛑 Cancelled pending partial for final transcription")
                
                # process final
                # DEDUPLICATION: Check if we already processed final for this turn
                if self._final_sent_for_turn == self.current_turn_id and not audio_chunks:
                    print(f"⚠️ Duplicate None signal for turn {self.current_turn_id}, skipping")
                    continue
                
                if audio_chunks:
                    print(f"📝 Processing {len(audio_chunks)} audio chunks")
                    
                    # Combine chunks
                    combined_audio = b''.join(audio_chunks)
                    
                    # Get final transcript
                    final_text = await self.stt.transcribe_final(combined_audio)
                    
                    if final_text and len(final_text.strip()) > 1:
                        print(f"✅ Final transcript: {final_text}")
                        
                        # Mark final as sent for this turn
                        self._final_sent_for_turn = self.current_turn_id
                        
                        # Trigger LLM ONLY on final results
                        await transcript_buffer.put({
                            'type': 'final',
                            'text': final_text,
                            'turn_id': self.current_turn_id,
                            'timestamp': time.time()
                        })
                        
                        # Send to client
                        await websocket.send(json.dumps({
                            'type': 'transcript_final',
                            'text': final_text
                        }))
                    else:
                        # FALLBACK: If we got audio but no text (STT failed)
                        # Only trigger if we had a reasonable amount of audio (> ~1s)
                        if len(audio_chunks) > 20: 
                            print("⚠️ STT produced no text. Sending fallback response.")
                            fallback_text = "I could not hear your words clearly, dear one. May you speak again with a calm heart?"
                            
                            await websocket.send(json.dumps({
                                'type': 'transcript_final',
                                'text': "[Inaudible Audio]"
                            }))
                            
                            # Fake an LLM token to make Krishna speak the fallback
                            await llm_token_buffer.put(fallback_text)
                            await llm_token_buffer.put(None) 
                        else:
                            print("⚠️ STT produced no text (Audio too short, likely noise).")

                    audio_chunks = []
                
                # IMPORTANT: Reset turn-level metrics to allow next trigger
                self.metrics['audio_received_at'] = 0
                self._chunk_count = 0
                continue
            
            # Every 10 chunks (~400ms) and if no partial is currently in flight
            if len(audio_chunks) >= 10 and (partial_task is None or partial_task.done()):
                # Skip partial during TTS playback
                if self.is_speaking:
                    continue
                
                # Throttle partials to every 500ms
                now = time.time()
                if now - last_partial_trigger_at < 0.5:
                    continue
                
                last_partial_trigger_at = now
                combined_audio = b''.join(audio_chunks)
                
                # Launch partial transcription as a task so it doesn't block the loop
                async def run_partial(audio, ws):
                    text = await self.stt.transcribe_partial(audio)
                    if text:
                        # Record timing
                        if self.metrics['stt_first_partial_at'] == 0:
                            self.metrics['stt_first_partial_at'] = time.time()
                            latency = (self.metrics['stt_first_partial_at'] - self._turn_start_time) * 1000
                            print(f"⚡ STT latency: {latency:.0f}ms")
                        
                        print(f"📝 Partial: {text}")
                        await ws.send(json.dumps({
                            'type': 'transcript_partial',
                            'text': text
                        }))

                partial_task = asyncio.create_task(run_partial(combined_audio, websocket))
    
    async def process_llm(self, transcript_buffer: asyncio.Queue, llm_token_buffer: asyncio.Queue, websocket: Any):
        """Process streaming LLM with token-by-token generation"""
        print("🧠 LLM processor started")
        
        while True:
            transcript_data = await transcript_buffer.get()
            
            user_text = transcript_data['text'].strip()
            is_final = transcript_data['type'] == 'final'
            turn_id = transcript_data.get('turn_id', 0)
            
            # FIXED Deduplication: Skip if already processing or already processed this turn
            if turn_id <= self.processed_turn_id:
                print(f"⚠️ Skipping duplicate turn {turn_id} (already processed {self.processed_turn_id})")
                continue
            
            # Skip empty text (but allow single words)
            if not user_text or len(user_text.strip()) < 1:
                print(f"⚠️ Skipping empty text")
                continue
            
            # Use lock to prevent concurrent LLM+TTS cycles
            async with self.processing_lock:
                # Double-check after acquiring lock
                if turn_id <= self.processed_turn_id:
                    continue
                    
                self.is_processing = True
                self.processed_turn_id = turn_id
                self.should_interrupt = False  # RESET INTERRUPTION FLAG FOR NEW TURN
                
                # FIXED: Metrics should be measured from when we get the FINAL transcript
                # This is the actual processing start time
                self.processing_start_time = time.time()
                self._turn_start_time = self.processing_start_time 
                
                print(f"🧠 LLM processing turn {turn_id}: {user_text}")
            
                # Signal to UI
                await websocket.send(json.dumps({
                    'type': 'state', 
                    'message': 'Krishna is thinking...', 
                    'status': 'processing'
                }))
                
                # Signal to UI
                await websocket.send(json.dumps({
                    'type': 'state', 
                    'message': 'Krishna is thinking...', 
                    'status': 'processing'
                }))
                
                # REFACTORED: Use streaming LLM for instant response
                assistant_full_response = ""
                current_sentence = ""
                
                try:
                    # NEW: Get intent and relevant verses first for better guidance
                    print(f"🎯 Classifying intent for: {user_text[:50]}...")
                    intent_data = await self.intent_classifier.classify_and_respond(user_text)
                    intent_category = intent_data.get("category", "Daily Struggles")
                    print(f"✅ Detected intent: {intent_category}")

                    # Stream Krishna's wise words with intent awareness
                    async for token in self.llm.get_intent_aware_response(user_text, intent_category, self.conversation_history):
                        if self.should_interrupt:
                            break
                        
                        assistant_full_response += token
                        current_sentence += token
                        
                        # Metrics on first token
                        if self.metrics['llm_first_token_at'] == 0:
                            self.metrics['llm_first_token_at'] = time.time()
                            latency = (self.metrics['llm_first_token_at'] - self._turn_start_time) * 1000
                            print(f"⚡ LLM first token latency: {latency:.0f}ms")

                        # Send token to client UI
                        await websocket.send(json.dumps({
                            'type': 'llm_token',
                            'token': token
                        }))
                        
                        # VERSE-LOCK & SMART CHUNKING: 
                        # 1. Don't split if we are inside a quote (Verse-Lock)
                        # 2. Trigger on sentence boundary or if it's getting long at a word boundary
                        
                        is_first_sentence = self.metrics['tts_first_audio_at'] == 0
                        threshold = 30 if is_first_sentence else 50
                        
                        # Count quotes in the assistant_full_response to see if we're in an open quote
                        in_quote = assistant_full_response.count('"') % 2 != 0
                        
                        # Only split if NOT in a quote OR if the verse is extremely long (>150 chars)
                        can_split = not in_quote or len(current_sentence) > 150
                        
                        if can_split and (any(punct in token for punct in ".!?।।\n,") or (len(current_sentence) > threshold and token.isspace())):
                            sentence_to_send = current_sentence.strip()
                            if sentence_to_send:
                                print(f"📤 Sending {'FAST ' if is_first_sentence else ''}{'VERSE ' if in_quote else ''}sentence to TTS: {sentence_to_send}")
                                await llm_token_buffer.put(sentence_to_send)
                            current_sentence = ""

                    # Send any remaining text
                    if current_sentence.strip() and not self.should_interrupt:
                        await llm_token_buffer.put(current_sentence.strip())

                except Exception as e:
                    print(f"❌ LLM Streaming Error: {e}")
                    error_msg = "My dear Partha, the worldly connection is weak. Please speak again."
                    await websocket.send(json.dumps({'type': 'llm_token', 'token': error_msg}))
                    await llm_token_buffer.put(error_msg)

                # Signal end of response
                await llm_token_buffer.put(None)
                
                # Store in conversation history
                if assistant_full_response.strip():
                    self.conversation_history.append({"role": "user", "content": user_text})
                    self.conversation_history.append({"role": "assistant", "content": assistant_full_response.strip()})
                    
                # Keep history manageable
                if len(self.conversation_history) > 10:
                    self.conversation_history = self.conversation_history[-10:]
                    
                # Print performance stats
                self._print_metrics()
                
                # === EVALUATE RESPONSE QUALITY ===
                if EVALUATION_ENABLED and assistant_full_response.strip():
                    try:
                        evaluator = get_evaluator()
                        eval_result = await evaluator.evaluate(
                            user_query=user_text,
                            krishna_response=assistant_full_response.strip(),
                            rag_context=""  # RAG context would be added here if tracked
                        )
                        evaluator.print_evaluation(eval_result)
                    except Exception as e:
                        print(f"⚠️ Evaluation skipped: {e}")
                
                # Reset for next turn
                self.metrics['audio_received_at'] = 0
                self.metrics['llm_first_token_at'] = 0
                self.metrics['tts_first_audio_at'] = 0
                self.is_processing = False
    
    async def process_tts(self, llm_token_buffer: asyncio.Queue, websocket: Any):
        """Process streaming TTS with sentence-by-sentence generation"""
        print("🔊 TTS processor started")
        
        while True:
            text = await llm_token_buffer.get()
            if text is None: # Handle end of response
                # End of LLM response
                await websocket.send(json.dumps({
                    'type': 'response_complete'
                }))
                
                # Print final metrics
                self._print_metrics()
                # Don't reset here, reset at start of next audio chunk
                continue
            
            if self.should_interrupt:
                print("⚠️ TTS interrupted")
                continue
            
            try:
                # Mark as speaking to stop receiving audio (feedback prevention)
                self.is_speaking = True
                await websocket.send(json.dumps({
                    'type': 'state', 
                    'message': 'Krishna is speaking...', 
                    'status': 'speaking'
                }))
                
                print(f"🔊 TTS generating: {text[:50]}...")
                
                # Streaming TTS
                first_chunk = True
                async for chunk in self.tts.stream_audio(text): # Changed from stream to stream_audio
                    if self.should_interrupt:
                        print("⚠️ TTS playback interrupted") # Added print for clarity
                        break
                    
                    if first_chunk:
                        # Metrics for first audio
                        self.metrics['tts_first_audio_at'] = time.time()
                        if self.metrics['llm_first_token_at'] > 0:
                            ttfa = (self.metrics['tts_first_audio_at'] - self.metrics['llm_first_token_at']) * 1000
                            print(f"⚡ TTS first audio latency (from LLM): {ttfa:.0f}ms")
                        first_chunk = False
                        
                    import base64
                    await websocket.send(json.dumps({
                        'type': 'audio_chunk', # Changed from 'audio' to 'audio_chunk'
                        'audio': base64.b64encode(chunk).decode('utf-8') # Changed from 'data' to 'audio'
                    }))
                
                # Signal chunk completion to client
                await websocket.send(json.dumps({'type': 'audio_complete'}))
                
                # Removed sleep to eliminate gap between sentences
                self.is_speaking = False
                await websocket.send(json.dumps({
                    'type': 'state', 
                    'message': 'Krishna finished speaking', 
                    'status': 'success'
                }))
                
            except Exception as e:
                print(f"❌ TTS Error: {e}")
                self.is_speaking = False
                await websocket.send(json.dumps({'type': 'state', 'state': 'idle'}))
    
    def _build_krishna_context(self, user_text: str) -> str:
        """Build Krishna-style context for LLM"""
        system_prompt = """You are Krishna, the divine guide from the Bhagavad Gita.
Speak with wisdom, compassion, and clarity. Keep responses concise and profound.
Address the user as 'dear one' or 'beloved friend'.
Provide practical spiritual guidance rooted in dharma."""
        
        # Add conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        for msg in self.conversation_history[-4:]:  # Last 4 exchanges
            messages.append(msg)
        
        messages.append({"role": "user", "content": user_text})
        
        return messages
    
    def _is_sentence_boundary(self, text: str) -> bool:
        """Check if text ends with sentence boundary"""
        return text.rstrip().endswith(('.', '!', '?', '।', '\n'))
    
    def _print_metrics(self):
        """Print performance metrics"""
        if self.metrics['audio_received_at'] == 0:
            return
        
        print("\n" + "="*50)
        print("📊 PERFORMANCE METRICS")
        print("="*50)
        
        base = self.metrics['audio_received_at']
        
        if self.metrics['stt_first_partial_at']:
            stt_latency = (self.metrics['stt_first_partial_at'] - base) * 1000
            print(f"🎯 STT First Partial: {stt_latency:.0f}ms")
        
        if self.metrics['llm_first_token_at']:
            llm_latency = (self.metrics['llm_first_token_at'] - base) * 1000
            print(f"🧠 LLM First Token: {llm_latency:.0f}ms")
        
        if self.metrics['tts_first_audio_at']:
            # THE "EXCELLENT" METRIC: User stopped speaking -> AI started speaking
            handoff_latency = (self.metrics['tts_first_audio_at'] - self.processing_start_time) * 1000
            print(f"⚡ HANDOFF LATENCY: {handoff_latency:.0f}ms (Target: <1500ms)")
            
            if handoff_latency < 1000:
                print("🌟 EXCELLENT - Sub-second handoff!")
            elif handoff_latency < 1500:
                print("✅ GREAT - Very responsive!")
            elif handoff_latency < 2500:
                print("⚠️ GOOD - Feels okay")
            else:
                print("❌ SLOW - Distance is too far")
        
        print("="*50 + "\n")
    
    def _reset_metrics(self):
        """Reset metrics for next interaction"""
        self.metrics = {
            'audio_received_at': 0,
            'stt_first_partial_at': 0,
            'llm_first_token_at': 0,
            'tts_first_audio_at': 0,
            'user_heard_at': 0
        }


async def main():
    """Start WebSocket server"""
    orchestrator = StreamingOrchestrator()
    
    print("="*60)
    print("🚀 KRISHNA REAL-TIME VOICE ASSISTANT")
    print("="*60)
    print("⚡ Optimized for <1 second latency")
    print("🎯 WebSocket server starting on port 8765")
    print("="*60 + "\n")
    
    async with websockets.serve(orchestrator.handle_client, "0.0.0.0", 8765):
        print("✅ Server ready! Waiting for connections...\n")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        print("DEBUG: Calling asyncio.run(main())")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")
    except Exception as e:
        print(f"\n❌ FATAL SERVER ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
