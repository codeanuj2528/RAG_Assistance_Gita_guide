"""
Configuration Management for Krishna Voice Assistant
OPTIMIZED FOR SPEED AND ACCURACY
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Central configuration class - OPTIMIZED"""
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    
    # Model Selection - OPTIMIZED FOR SPEED
    USE_GROQ = os.getenv("USE_GROQ", "True").lower() == "true"  # Groq is MUCH faster
    
    # STT Configuration (Whisper)
    WHISPER_MODEL = "whisper-1"
    
    # LLM Configuration - OPTIMIZED
    OPENAI_MODEL = "gpt-4o-mini"  # Fast and accurate
    GROQ_MODEL = "llama-3.3-70b-versatile"  # Instant & high rate limits
    
    # TTS Configuration - OPTIMIZED FOR KRISHNA VOICE
    # Best Krishna-like voices (deep, wise, warm):
    # "pNInz6obpgDQGcFmaJgB" - Adam (deep, authoritative) - DEFAULT
    # "21m00Tcm4TlvDq8ikWAM" - Rachel (warm, gentle, female)
    # "onwK4e9ZLuTAKqWW03F9" - Daniel (calm, wise, male)
    
    
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    ELEVENLABS_MODEL = "eleven_turbo_v2_5"  # Fastest model
    
    # OpenAI TTS Voice (Best options for Krishna)
    # nova = warm, gentle, clear (BEST - lightest voice)
    # alloy = neutral, balanced
    # onyx = deep, smooth (too heavy)
    OPENAI_VOICE = os.getenv("OPENAI_VOICE", "nova") 
    
    # OPTIMIZED VOICE SETTINGS FOR KRISHNA (deep, spiritual feel)
    ELEVENLABS_STABILITY = 0.82      # Higher stability for steady delivery of verses
    ELEVENLABS_SIMILARITY = 0.85     # Keep original voice characteristics
    ELEVENLABS_STYLE = 0.65           # Better emotional depth for wise delivery
    ELEVENLABS_SPEAKER_BOOST = True  # Enhance clarity
    
    # Intent Categories
    INTENT_CATEGORIES = [
        "Career/Purpose",
        "Relationships", 
        "Inner Conflict",
        "Life Transitions",
        "Daily Struggles"
    ]
    
    # Audio Settings
    SAMPLE_RATE = 16000
    CHANNELS = 1
    SILENCE_THRESHOLD = 500  # milliseconds (Faster auto-trigger)
    
    # RAG Configuration - OPEN SOURCE & FAST
    RAG_ENABLED = os.getenv("RAG_ENABLED", "True").lower() == "true"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Fast (16ms) & free
    VECTOR_DB_PATH = "./chroma_db"
    COLLECTION_NAME = "bhagavad_gita_verses"
    TOP_K_RETRIEVAL = 3  # Retrieve top 3 most relevant verses
    RAG_SIMILARITY_THRESHOLD = 0.2  # Minimum similarity score (lowered for better recall)
    
    @classmethod
    def validate(cls):
        """Validate required API keys"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required in .env file")
        
        if cls.USE_GROQ and not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY required when USE_GROQ=True")
        
        return True

# Validate on import
Config.validate()
