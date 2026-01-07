"""
RAG Embedder - One-Time Embedding Script
Creates vector database from Bhagavad Gita JSON files

RUN THIS ONCE BEFORE USING THE ASSISTANT:
    python rag_embedder.py

This will:
1. Load all JSON files from data/ folder
2. Create structured text chunks
3. Generate embeddings using all-MiniLM-L6-v2
4. Store in ChromaDB for fast retrieval

Expected time: 2-5 minutes (one-time only)
"""

import os
import json
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from config import Config


class BhagavadGitaEmbedder:
    """One-time embedder for Gita verses"""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize embedder
        
        Args:
            data_dir: Directory containing JSON files
        """
        self.data_dir = data_dir
        
        # Load embedding model
        print(f"📥 Loading embedding model: {Config.EMBEDDING_MODEL}")
        print("   (First run will download ~80MB model)")
        self.model = SentenceTransformer(Config.EMBEDDING_MODEL)
        print("✅ Model loaded!")
        
        # Initialize ChromaDB
        print(f"\n📁 Initializing vector database at: {Config.VECTOR_DB_PATH}")
        self.client = chromadb.PersistentClient(path=Config.VECTOR_DB_PATH)
        
    def load_json_file(self, filename: str) -> Dict:
        """Load and parse JSON file"""
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️ Warning: {filename} not found at {filepath}")
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_verse_chunks(self) -> List[Dict]:
        """
        Create structured text chunks from JSON files
        
        Returns:
            List of dicts with 'text', 'metadata'
        """
        print("\n📚 Loading JSON files...")
        
        # Load all JSON files
        verses = self.load_json_file("verse.json")
        translations = self.load_json_file("translation.json")
        commentaries = self.load_json_file("commentary.json")
        chapters = self.load_json_file("chapters.json")
        authors = self.load_json_file("authors.json")
        languages = self.load_json_file("languages.json")
        
        if not verses:
            raise FileNotFoundError(
                f"❌ No verse.json found in '{self.data_dir}/' directory!\n"
                f"   Please create a 'data/' folder and add all JSON files."
            )
        
        print(f"✅ Loaded {len(verses)} verses")
        
        # Create lookup dicts
        chapter_dict = {ch.get('id'): ch for ch in chapters} if chapters else {}
        author_dict = {au.get('id'): au for au in authors} if authors else {}
        lang_dict = {la.get('id'): la for la in languages} if languages else {}
        
        # Group translations and commentaries by verse_id
        trans_by_verse = {}
        for trans in translations:
            verse_id = trans.get('verse_id')
            if verse_id not in trans_by_verse:
                trans_by_verse[verse_id] = []
            trans_by_verse[verse_id].append(trans)
        
        comm_by_verse = {}
        for comm in commentaries:
            verse_id = comm.get('verse_id')
            if verse_id not in comm_by_verse:
                comm_by_verse[verse_id] = []
            comm_by_verse[verse_id].append(comm)
        
        # Create chunks
        print("\n🔨 Creating structured text chunks...")
        chunks = []
        
        for verse in verses:
            verse_id = verse.get('id')
            chapter_id = verse.get('chapter_id')
            verse_number = verse.get('verse_number')
            
            # Get chapter info
            chapter_info = chapter_dict.get(chapter_id, {})
            chapter_name = chapter_info.get('name', 'Unknown')
            
            # Base verse info
            sanskrit_text = verse.get('text', '')
            transliteration = verse.get('transliteration', '')
            word_meanings = verse.get('word_meanings', '')
            
            # Get translations for this verse
            verse_translations = trans_by_verse.get(verse_id, [])
            
            # Get commentaries for this verse
            verse_commentaries = comm_by_verse.get(verse_id, [])
            
            # Create chunk for primary (English) translation
            for trans in verse_translations:
                lang_id = trans.get('language_id')
                lang_info = lang_dict.get(lang_id, {})
                lang_name = lang_info.get('language', 'Unknown')
                
                author_id = trans.get('author_id')
                author_info = author_dict.get(author_id, {})
                author_name = author_info.get('name', 'Unknown')
                
                translation_text = trans.get('description', '')
                
                # Find matching commentary from same author
                matching_commentary = ""
                for comm in verse_commentaries:
                    if comm.get('author_id') == author_id:
                        matching_commentary = comm.get('description', '')
                        break
                
                # Build structured text
                text_parts = [
                    "Scripture: Bhagavad Gita",
                    f"Chapter: {chapter_id} - {chapter_name}",
                    f"Verse: {verse_number}",
                    "",
                    "Sanskrit Verse:",
                    sanskrit_text,
                    ""
                ]
                
                if transliteration:
                    text_parts.extend([
                        "Transliteration:",
                        transliteration,
                        ""
                    ])
                
                if word_meanings:
                    text_parts.extend([
                        "Word Meanings:",
                        word_meanings,
                        ""
                    ])
                
                if translation_text:
                    text_parts.extend([
                        f"Translation ({lang_name}):",
                        translation_text,
                        ""
                    ])
                
                if matching_commentary:
                    text_parts.extend([
                        f"Commentary ({author_name}):",
                        matching_commentary,
                        ""
                    ])
                
                chunk_text = "\n".join(text_parts)
                
                # Create metadata
                metadata = {
                    "chapter": chapter_id,
                    "verse": verse_number,
                    "chapter_name": chapter_name,
                    "language": lang_name,
                    "scripture": "Bhagavad Gita",
                    "type": "verse",
                    "has_word_meanings": bool(word_meanings),
                    "has_commentary": bool(matching_commentary),
                    "author": author_name,
                    "verse_id": str(verse_id)
                }
                
                chunks.append({
                    "text": chunk_text,
                    "metadata": metadata,
                    "id": f"v{verse_id}_t{author_id}_{lang_id}"
                })
        
        print(f"✅ Created {len(chunks)} text chunks")
        return chunks
    
    def embed_and_store(self, chunks: List[Dict]):
        """
        Generate embeddings and store in ChromaDB
        
        Args:
            chunks: List of chunk dicts with 'text', 'metadata', 'id'
        """
        # Check if collection already exists
        try:
            existing_collection = self.client.get_collection(name=Config.COLLECTION_NAME)
            print(f"\n⚠️ Collection '{Config.COLLECTION_NAME}' already exists!")
            
            response = input("   Delete and recreate? (yes/no): ").strip().lower()
            if response == 'yes':
                self.client.delete_collection(name=Config.COLLECTION_NAME)
                print("   ✅ Deleted existing collection")
            else:
                print("   ❌ Aborted. Using existing embeddings.")
                return
        except:
            pass  # Collection doesn't exist, continue
        
        # Create collection
        print(f"\n🔧 Creating collection: {Config.COLLECTION_NAME}")
        collection = self.client.create_collection(
            name=Config.COLLECTION_NAME,
            metadata={"description": "Bhagavad Gita verses with translations and commentary"}
        )
        
        # Batch embedding for efficiency
        print(f"\n⚡ Generating embeddings for {len(chunks)} chunks...")
        print("   This may take 2-5 minutes...")
        
        batch_size = 50  # Process in batches
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            print(f"   Processing batch {batch_num}/{total_batches}...")
            
            # Extract data
            texts = [chunk['text'] for chunk in batch]
            metadatas = [chunk['metadata'] for chunk in batch]
            ids = [chunk['id'] for chunk in batch]
            
            # Generate embeddings
            embeddings = self.model.encode(texts, convert_to_tensor=False, show_progress_bar=False)
            
            # Store in ChromaDB
            collection.add(
                documents=texts,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )
        
        print(f"\n✅ Successfully embedded and stored {len(chunks)} chunks!")
        print(f"   Vector database saved at: {Config.VECTOR_DB_PATH}")
    
    def run(self):
        """Main embedding pipeline"""
        print("=" * 60)
        print("🕉️  BHAGAVAD GITA RAG EMBEDDER")
        print("=" * 60)
        
        # Check if data directory exists
        if not os.path.exists(self.data_dir):
            print(f"\n❌ ERROR: '{self.data_dir}/' directory not found!")
            print(f"\nPlease create the directory and add these JSON files:")
            print("  - verse.json")
            print("  - translation.json")
            print("  - commentary.json")
            print("  - chapters.json")
            print("  - authors.json")
            print("  - languages.json")
            return
        
        try:
            # Create chunks
            chunks = self.create_verse_chunks()
            
            if not chunks:
                print("\n❌ No chunks created. Check your JSON files!")
                return
            
            # Embed and store
            self.embed_and_store(chunks)
            
            print("\n" + "=" * 60)
            print("✅ EMBEDDING COMPLETE!")
            print("=" * 60)
            print("\nYou can now run the Krishna Voice Assistant:")
            print("  python launch.py")
            print("\nThe embeddings are cached and won't need to be recreated.")
            
        except Exception as e:
            print(f"\n❌ Error during embedding: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    embedder = BhagavadGitaEmbedder()
    embedder.run()
