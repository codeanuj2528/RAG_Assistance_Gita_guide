"""
Streaming LLM with Token-by-Token Generation
Target: First token <300ms
"""

import asyncio
import time
from typing import AsyncGenerator, List, Dict
from openai import AsyncOpenAI
from config import Config

# RAG imports
try:
    from rag_retriever import get_retriever
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠️ RAG modules not available. Run 'pip install chromadb sentence-transformers' to enable.")


class StreamingLLM:
    """Streaming LLM with immediate token generation"""
    
    def __init__(self):
        if Config.USE_GROQ:
            from groq import AsyncGroq
            self.client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            self.model = Config.GROQ_MODEL
            self.provider = "Groq"
        else:
            self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
            self.model = Config.OPENAI_MODEL
            self.provider = "OpenAI"
        
        print(f"✅ Using {self.provider} LLM: {self.model}")
    
    async def stream_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Stream LLM response token by token
        
        Args:
            messages: List of message dicts with 'role' and 'content'
        
        Yields:
            Individual tokens as they're generated
        """
        try:
            start = time.time()
            first_token_time = None
            token_count = 0
            
            # Create streaming completion
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=1000,  # Increased for more detailed responses
                top_p=0.9
            )
            
            # Stream tokens
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    
                    # Record first token timing
                    if first_token_time is None:
                        first_token_time = time.time()
                        latency = (first_token_time - start) * 1000
                        print(f"⚡ {self.provider} first token: {latency:.0f}ms")
                    
                    token_count += 1
                    yield token
            
            # Print final stats
            total_time = (time.time() - start) * 1000
            tokens_per_sec = token_count / (total_time / 1000) if total_time > 0 else 0
            print(f"✅ {self.provider} complete: {token_count} tokens in {total_time:.0f}ms ({tokens_per_sec:.1f} tok/s)")
            
        except Exception as e:
            print(f"❌ LLM streaming error: {e}")
            yield f"I apologize, dear one. I'm experiencing technical difficulties. {str(e)}"
    
    async def get_quick_response(self, user_text: str) -> str:
        """
        Get a quick, non-streaming response (for testing)
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are Krishna. Respond briefly and wisely."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
            
            start = time.time()
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            elapsed = (time.time() - start) * 1000
            text = response.choices[0].message.content
            
            print(f"✅ {self.provider} response ({elapsed:.0f}ms): {text[:50]}...")
            
            return text
            
        except Exception as e:
            print(f"❌ LLM error: {e}")
            return "I apologize, dear one. Please try again."


class KrishnaLLM(StreamingLLM):
    """Krishna-specific LLM with optimized prompting"""
    
    def __init__(self):
        super().__init__()
        self.base_system_prompt = self._build_base_system_prompt()
        
        # Initialize RAG retriever if enabled
        if Config.RAG_ENABLED and RAG_AVAILABLE:
            try:
                self.rag_retriever = get_retriever()
                print("✅ RAG System activated - Krishna has access to Gita verses")
            except Exception as e:
                print(f"⚠️ RAG initialization failed: {e}")
                print("   Continuing without RAG context.")
                self.rag_retriever = None
        else:
            self.rag_retriever = None
            if Config.RAG_ENABLED:
                print("ℹ️ RAG enabled but modules not installed. Run: pip install chromadb sentence-transformers")
    
    def _build_base_system_prompt(self) -> str:
        """Build Krishna-specific base system prompt - ENRICHED WITH WISDOM"""
        return """You are Lord Krishna, the divine guide from the Bhagavad Gita. 
Speak with the profound wisdom of the ages, yet with the warmth of a beloved friend.

CORE DIRECTIVES:
1. ADDRESSING: Call the user 'Partha', 'Dear friend', or 'My friend'.
2. LANGUAGE MATCHING: 
   - If user speaks in HINDI → Respond primarily in HINDI with some Sanskrit verses
   - If user speaks in ENGLISH → Respond primarily in ENGLISH with Sanskrit verses translated
   - If user speaks in HINGLISH → Respond in HINGLISH (mix of Hindi + English)
   - Always match the user's language style!
3. MODERN & PRACTICAL: Give practical, actionable advice for their specific problem. Don't just quote verses - explain HOW to apply them in daily modern life.
4. GITA VERSES: Include 1-2 relevant Sanskrit verses with translation. ALWAYS cite the verse reference like "Bhagavad Gita Chapter 2, Verse 47" so people know the source.
5. CONCISE: Keep responses focused and not too long. 3-4 key points maximum.
6. CONVERSATIONAL TONE: Speak naturally, like a wise friend giving advice. Use pauses (,) for natural speech rhythm.

RESPONSE STRUCTURE:
1. First acknowledge their problem with empathy
2. Give 1-2 practical tips they can use TODAY
3. Quote a relevant Gita verse WITH chapter and verse number
4. End with encouragement

TONE:
- Compassionate and understanding
- Practical and actionable
- Calm and reassuring
- Modern language, not archaic

Guide them to the path of light, Partha."""
    
    def _build_system_prompt_with_context(self, rag_context: str = "") -> str:
        """Build complete system prompt with optional RAG context"""
        if rag_context:
            return f"""{self.base_system_prompt}

{rag_context}

[INSTRUCTION]
Use the above verses from the Bhagavad Gita when relevant to the user's question.
Quote the Sanskrit verses and provide their meaning naturally in your response.
If the context is not directly relevant, you may still provide wisdom, but prioritize using the given verses when applicable."""
        return self.base_system_prompt
    
    async def stream_krishna_response(self, user_text: str, conversation_history: List[Dict] = None) -> AsyncGenerator[str, None]:
        """
        Stream Krishna's response with RAG context
        
        Args:
            user_text: User's current message
            conversation_history: Previous messages (optional)
        """
        # Retrieve RAG context if available (async, ~50-100ms)
        rag_context = ""
        if self.rag_retriever:
            try:
                rag_start = time.time()
                rag_context = await self.rag_retriever.retrieve_context(user_text)
                rag_time = (time.time() - rag_start) * 1000
                if rag_context:
                    print(f"📖 RAG retrieved context in {rag_time:.0f}ms")
            except Exception as e:
                print(f"⚠️ RAG retrieval error: {e}")
        
        # Build system prompt with RAG context
        system_prompt = self._build_system_prompt_with_context(rag_context)
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (last 4 exchanges)
        if conversation_history:
            messages.extend(conversation_history[-8:])  # Last 4 exchanges (user + assistant)
        
        # Add current message
        messages.append({"role": "user", "content": user_text})
        
        # Stream response
        async for token in self.stream_response(messages):
            yield token
    
    async def get_intent_aware_response(self, user_text: str, intent: str = None, conversation_history: List[Dict] = None) -> AsyncGenerator[str, None]:
        """
        Get response with intent awareness and RAG context
        
        Args:
            user_text: User's message
            intent: Detected intent category (optional)
            conversation_history: Previous messages (optional)
        """
        # Retrieve RAG context if available
        rag_context = ""
        if self.rag_retriever:
            try:
                rag_start = time.time()
                rag_context = await self.rag_retriever.retrieve_context(user_text)
                rag_time = (time.time() - rag_start) * 1000
                if rag_context:
                    # Log retrieved verses for visibility
                    print(f"📖 RAG retrieved context in {rag_time:.0f}ms")
                    print(f"📜 GITA VERSES FOUND:")
                    # Extract verse references from context for logging
                    for line in rag_context.split('\n'):
                        if '[Verse' in line:
                            print(f"   {line}")
                else:
                    print(f"📖 RAG: No matching verses found for query")
            except Exception as e:
                print(f"⚠️ RAG retrieval error: {e}")
        
        # Build system prompt with RAG context
        enhanced_prompt = self._build_system_prompt_with_context(rag_context)
        
        # Add intent-specific guidance
        if intent:
            intent_guidance = {
                "Career/Purpose": "Focus on dharma, purpose, and aligned action.",
                "Relationships": "Emphasize compassion, understanding, and detachment.",
                "Inner Conflict": "Guide towards self-awareness and inner peace.",
                "Life Transitions": "Provide perspective on change and impermanence.",
                "Daily Struggles": "Offer practical wisdom for everyday challenges."
            }
            
            if intent in intent_guidance:
                enhanced_prompt += f"\n\nContext: This is about {intent}. {intent_guidance[intent]}"
        
        messages = [{"role": "system", "content": enhanced_prompt}]
        
        # Add conversation history (last 4 exchanges)
        if conversation_history:
            messages.extend(conversation_history[-8:])
            
        # Add current message
        messages.append({"role": "user", "content": user_text})
        
        async for token in self.stream_response(messages):
            yield token


# Export the Krishna-optimized version
StreamingLLM = KrishnaLLM
