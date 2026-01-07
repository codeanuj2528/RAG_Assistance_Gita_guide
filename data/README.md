# 📁 Data Files Required

This folder should contain the following JSON files from Bhagavad Gita:

## Required Files:
- ✅ `verse.json` - All Gita verses with Sanskrit text
- ✅ `translation.json` - Translations in various languages
- ✅ `commentary.json` - Commentaries from various authors
- ✅ `chapters.json` - Chapter information
- ✅ `authors.json` - Author/translator information
- ✅ `languages.json` - Language metadata

## After adding files:

Run the embedder script from the parent directory:
```bash
cd ..
python rag_embedder.py
```

This will process all files and create the vector database for fast retrieval.
