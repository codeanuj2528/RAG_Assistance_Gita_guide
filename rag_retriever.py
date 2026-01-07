"""
RAG Retriever - Runtime Context Retrieval
Fast open-source embeddings with <100ms latency
"""

import asyncio
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from config import Config


class RAGRetriever:
    """Fast retrieval using all-MiniLM-L6-v2 embeddings"""
    
    def __init__(self):
        """Initialize retriever with cached model and DB connection"""
        print("🔍 Initializing RAG Retriever...")
        
        # Load embedding model (once, at startup)
        self.model = SentenceTransformer(Config.EMBEDDING_MODEL)
        print(f"✅ Loaded embedding model: {Config.EMBEDDING_MODEL}")
        
        # Connect to ChromaDB
        self.client = chromadb.PersistentClient(path=Config.VECTOR_DB_PATH)
        
        # Get collection (will fail if not created yet)
        try:
            self.collection = self.client.get_collection(name=Config.COLLECTION_NAME)
            verse_count = self.collection.count()
            print(f"✅ Connected to vector DB: {verse_count} verses indexed")
        except Exception as e:
            print(f"⚠️ No vector database found. Run 'python rag_embedder.py' first!")
            print(f"   Error: {e}")
            self.collection = None
    
    def _enhance_query(self, query: str) -> str:
        """
        Enhance query by mapping real-life problems to Gita concepts
        
        Examples:
        - "failure" → "Arjuna despair duty dharma"
        - "anxiety" → "fear worry mind control steadiness"
        """
        query_lower = query.lower()
        
        # Concept mappings: real-life problems → Gita concepts
        concept_map = {
            # Emotional struggles
            'failure': 'Arjuna despair duty dharma purpose',
            'fail': 'Arjuna despair duty dharma',
            'anxiety': 'fear mind control sthitaprajna steadiness peace',
            'anxious': 'fear worry mind steadiness',
            'fear': 'courage Arjuna warrior fearlessness abhaya',
            'worried': 'mind control meditation peace',
            'stress': 'mind control peace equanimity sama',
            'depression': 'despair Arjuna grief sorrow',
            'sad': 'grief sorrow Arjuna',
            'angry': 'anger krodha desire mind control',
            'anger': 'krodha desire lust mind control',
            
            # Life situations
            'loss': 'impermanence death eternal soul atman',
            'death': 'soul atman eternal imperishable',
            'die': 'soul atman eternal death rebirth',
            'change': 'impermanence eternal soul nature',
            'transition': 'change impermanence yoga',
            
            # Purpose & meaning
            'purpose': 'dharma duty swadharma calling',
            'meaning': 'dharma purpose duty life',
            'confused': 'Arjuna confusion duty dharma choice',
            'doubt': 'Arjuna doubt confusion faith',
            'lost': 'path dharma purpose guidance',
            
            # Relationships
            'relationship': 'detachment love compassion duty',
            'family': 'duty dharma attachment detachment',
            'love': 'bhakti devotion compassion',
            
            # Work & action
            'work': 'karma yoga action nishkam work duty',
            'career': 'dharma swadharma duty work karma',
            'job': 'karma yoga duty work nishkam',
            'action': 'karma yoga nishkam fruits results',
            
            # Spiritual concepts
            'god': 'Krishna Bhagavan divine supreme',
            'soul': 'atman self eternal imperishable',
            'self': 'atman soul consciousness awareness',
            'meditation': 'dhyana yoga mind control focus',
            'peace': 'shanti equanimity mind control sama',
            'happiness': 'sukha contentment equanimity joy',
            'suffering': 'dukha pain impermanence detachment',
        }
        
        # Find matching concepts
        enhanced_terms = [query]  # Always include original
        
        for keyword, gita_concepts in concept_map.items():
            if keyword in query_lower:
                enhanced_terms.append(gita_concepts)
        
        # Join all terms
        enhanced_query = ' '.join(enhanced_terms)
        
        return enhanced_query
    
    async def retrieve_context(self, query: str, top_k: int = None) -> str:
        """
        Retrieve relevant Gita verses for a query
        
        Args:
            query: User's question/message
            top_k: Number of results (default: Config.TOP_K_RETRIEVAL)
            
        Returns:
            Formatted context string with relevant verses
            
        Latency: ~50-100ms total
        """
        if not self.collection:
            return ""
        
        try:
            # Use config default if not specified
            if top_k is None:
                top_k = Config.TOP_K_RETRIEVAL
            
            # Enhance query with Gita concepts
            enhanced_query = self._enhance_query(query)
            
            # Log if query was enhanced
            if enhanced_query != query:
                print(f"🔍 Enhanced query: '{query}' → includes Gita concepts")
            
            # Embed enhanced query (~16ms)
            query_embedding = await asyncio.to_thread(
                self.model.encode,
                enhanced_query,
                convert_to_tensor=False
            )
            
            # Search vector DB (~20-30ms)
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k
            )
            
            # Format context (~10-20ms)
            context = self._format_context(results)
            
            return context
            
        except Exception as e:
            print(f"⚠️ RAG retrieval error: {e}")
            return ""
    
    def _format_context(self, results: Dict) -> str:
        """
        Format retrieved chunks into readable context
        
        Args:
            results: ChromaDB query results
            
        Returns:
            Formatted string with verse information
        """
        if not results or not results['documents'] or not results['documents'][0]:
            return ""
        
        documents = results['documents'][0]
        metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(documents)
        distances = results['distances'][0] if results['distances'] else [0] * len(documents)
        
        # Filter by similarity threshold (distance < threshold means more similar)
        filtered_verses = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB uses L2 distance, lower is better
            # Convert to similarity score (1 - normalized_distance)
            similarity = 1 - min(dist / 2, 1)  # Normalize to 0-1 range
            
            if similarity >= Config.RAG_SIMILARITY_THRESHOLD:
                filtered_verses.append({
                    'content': doc,
                    'metadata': meta,
                    'similarity': similarity
                })
        
        if not filtered_verses:
            return ""
        
        # Build formatted context
        context_parts = ["=== RELEVANT SCRIPTURE CONTEXT ===\n"]
        
        for i, verse in enumerate(filtered_verses, 1):
            meta = verse['metadata']
            chapter = meta.get('chapter', '?')
            verse_num = meta.get('verse', '?')
            
            context_parts.append(f"\n[Verse {i}: Chapter {chapter}, Verse {verse_num}]")
            context_parts.append(verse['content'])
            context_parts.append("")  # Blank line between verses
        
        context_parts.append("=== END CONTEXT ===")
        
        return "\n".join(context_parts)
    
    def get_verse_by_reference(self, chapter: int, verse: int) -> Optional[str]:
        """
        Get specific verse by chapter and verse number
        
        Args:
            chapter: Chapter number
            verse: Verse number
            
        Returns:
            Verse content or None if not found
        """
        if not self.collection:
            return None
        
        try:
            results = self.collection.get(
                where={
                    "$and": [
                        {"chapter": chapter},
                        {"verse": verse}
                    ]
                }
            )
            
            if results and results['documents']:
                return results['documents'][0]
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error fetching verse {chapter}.{verse}: {e}")
            return None


# Singleton instance (loaded once)
_retriever_instance = None

def get_retriever() -> RAGRetriever:
    """Get or create singleton retriever instance"""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()
    return _retriever_instance
