"""
RAG Retriever - LIGHTWEIGHT VERSION for Render Free Tier
Uses keyword-based search instead of embeddings to stay under 512MB
"""

import asyncio
import json
import os
from typing import List, Dict, Optional
from pathlib import Path


class LightweightRetriever:
    """
    Keyword-based retriever that works within 512MB memory limit.
    Uses pre-indexed keywords instead of embedding model.
    """
    
    def __init__(self):
        """Initialize with keyword index from data files"""
        print("🔍 Initializing Lightweight RAG Retriever...")
        
        self.verses = []
        self._load_verses()
        
        print(f"✅ Loaded {len(self.verses)} verses (keyword-based, no ML model)")
    
    def _load_verses(self):
        """Load verses from data files"""
        data_dir = Path(__file__).parent / "data"
        
        # Load translations
        translation_file = data_dir / "translation.json"
        verse_file = data_dir / "verse.json"
        
        translations = {}
        verses = {}
        
        try:
            if translation_file.exists():
                with open(translation_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
            
            if verse_file.exists():
                with open(verse_file, 'r', encoding='utf-8') as f:
                    verses = json.load(f)
            
            # Build searchable index
            for key, translation in translations.items():
                # Parse key format "chapter.verse"
                parts = key.split('.')
                if len(parts) >= 2:
                    chapter = parts[0]
                    verse = parts[1]
                    
                    sanskrit = verses.get(key, {}).get('text', '')
                    transliteration = verses.get(key, {}).get('transliteration', '')
                    
                    # Get first author's translation
                    if isinstance(translation, dict):
                        text = list(translation.values())[0] if translation else ''
                    else:
                        text = str(translation)
                    
                    self.verses.append({
                        'chapter': int(chapter),
                        'verse': int(verse),
                        'text': text,
                        'sanskrit': sanskrit,
                        'transliteration': transliteration,
                        'keywords': self._extract_keywords(text)
                    })
                    
        except Exception as e:
            print(f"⚠️ Error loading verses: {e}")
    
    def _extract_keywords(self, text: str) -> set:
        """Extract lowercase keywords from text"""
        if not text:
            return set()
        
        # Simple word extraction
        words = text.lower().split()
        # Remove punctuation
        clean_words = set()
        for word in words:
            clean = ''.join(c for c in word if c.isalnum())
            if len(clean) > 2:  # Skip very short words
                clean_words.add(clean)
        
        return clean_words
    
    def _get_gita_keywords(self, query: str) -> set:
        """Map query terms to Gita concepts"""
        query_lower = query.lower()
        
        concept_map = {
            'failure': {'duty', 'dharma', 'action', 'despair', 'arjuna'},
            'fail': {'duty', 'dharma', 'action'},
            'anxiety': {'fear', 'mind', 'peace', 'control', 'steady'},
            'fear': {'courage', 'fearless', 'warrior', 'death'},
            'stress': {'mind', 'peace', 'equanimity', 'calm'},
            'depression': {'despair', 'grief', 'sorrow', 'arise'},
            'sad': {'grief', 'sorrow', 'tears'},
            'angry': {'anger', 'desire', 'control', 'lust'},
            'death': {'soul', 'eternal', 'immortal', 'body', 'atman'},
            'purpose': {'dharma', 'duty', 'action', 'calling'},
            'confused': {'doubt', 'confusion', 'arjuna', 'clarity'},
            'lost': {'path', 'guidance', 'dharma', 'direction'},
            'work': {'karma', 'action', 'duty', 'fruit', 'result'},
            'career': {'dharma', 'duty', 'work', 'action'},
            'relationship': {'attachment', 'love', 'duty', 'compassion'},
            'meditation': {'yoga', 'mind', 'focus', 'concentration'},
            'peace': {'equanimity', 'calm', 'tranquil', 'steady'},
            'happiness': {'joy', 'bliss', 'contentment', 'pleasure'},
        }
        
        keywords = set()
        
        # Add original query words
        words = query_lower.split()
        for word in words:
            clean = ''.join(c for c in word if c.isalnum())
            if len(clean) > 2:
                keywords.add(clean)
        
        # Add mapped Gita concepts
        for term, concepts in concept_map.items():
            if term in query_lower:
                keywords.update(concepts)
        
        return keywords
    
    async def retrieve_context(self, query: str, top_k: int = 3) -> str:
        """
        Retrieve relevant verses using keyword matching
        
        Args:
            query: User's question
            top_k: Number of verses to return
            
        Returns:
            Formatted context string
        """
        if not self.verses:
            return ""
        
        try:
            # Get query keywords
            query_keywords = self._get_gita_keywords(query)
            
            if not query_keywords:
                return ""
            
            # Score each verse by keyword matches
            scored_verses = []
            for verse in self.verses:
                score = len(query_keywords & verse['keywords'])
                if score > 0:
                    scored_verses.append((score, verse))
            
            # Sort by score and get top_k
            scored_verses.sort(key=lambda x: x[0], reverse=True)
            top_verses = scored_verses[:top_k]
            
            if not top_verses:
                return ""
            
            # Format context
            context_parts = ["=== RELEVANT SCRIPTURE CONTEXT ===\n"]
            
            for i, (score, verse) in enumerate(top_verses, 1):
                context_parts.append(f"\n[Verse {i}: Chapter {verse['chapter']}, Verse {verse['verse']}]")
                context_parts.append(verse['text'])
                context_parts.append("")
            
            context_parts.append("=== END CONTEXT ===")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            print(f"⚠️ Retrieval error: {e}")
            return ""
    
    def get_verse_by_reference(self, chapter: int, verse: int) -> Optional[str]:
        """Get specific verse by reference"""
        for v in self.verses:
            if v['chapter'] == chapter and v['verse'] == verse:
                return v['text']
        return None


# MEMORY-EFFICIENT: Check if we should use lightweight or full retriever
_retriever_instance = None

def get_retriever():
    """Get retriever instance - uses lightweight version for low memory environments"""
    global _retriever_instance
    
    if _retriever_instance is None:
        # Check if we're in a memory-constrained environment
        use_lightweight = os.environ.get('LIGHTWEIGHT_RAG', 'true').lower() == 'true'
        
        if use_lightweight:
            print("💡 Using Lightweight RAG (keyword-based, low memory)")
            _retriever_instance = LightweightRetriever()
        else:
            # Import heavy version only if needed
            from sentence_transformers import SentenceTransformer
            import chromadb
            
            # Full RAG implementation would go here
            # But for Render free tier, we use lightweight
            _retriever_instance = LightweightRetriever()
    
    return _retriever_instance


# Export lightweight as default for Render
RAGRetriever = LightweightRetriever
