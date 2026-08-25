"""
JARVIS Plugin: vector_memory_rag
Provides semantic vector search and retrieval-augmented generation (RAG) over documents, notes, and code.
"""
import os
from pathlib import Path
from typing import Any, Dict, List

PLUGIN = {
    "name": "vector_memory_rag",
    "description": (
        "Belgeleri, notları veya kodları vektörel hafızaya kaydeder ve "
        "anlamsal arama (semantic search) ile en alakalı içerikleri anında getirir."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Yapılacak işlem: 'add_document', 'search_memory', 'list_collections'",
            },
            "content": {
                "type": "STRING",
                "description": "Hafızaya eklenecek metin veya taranacak arama sorgusu.",
            },
            "metadata": {
                "type": "OBJECT",
                "description": "İsteğe bağlı belge meta verileri (kaynak, başlık, etiketler).",
            },
            "top_k": {
                "type": "INTEGER",
                "description": "Getirilecek en alakalı sonuç sayısı (varsayılan: 3).",
            },
        },
        "required": ["action"],
    },
}

_CHROMA_DIR = Path(__file__).resolve().parent.parent / "memory" / "chroma_db"


def _get_client():
    try:
        import chromadb
        _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(_CHROMA_DIR))
    except Exception as e:
        return None


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip()
    content = str(parameters.get("content", "")).strip()
    top_k = int(parameters.get("top_k", 3))
    metadata = parameters.get("metadata") or {}

    client = _get_client()
    if not client:
        return "ChromaDB istemcisi yüklenemedi. chromadb kütüphanesinin kurulu olduğundan emin olun."

    collection = client.get_or_create_collection(name="jarvis_knowledge")

    if action == "add_document":
        if not content:
            return "Hafızaya eklenecek içerik belirtilmedi."
        import uuid
        doc_id = str(uuid.uuid4())[:8]
        collection.add(
            documents=[content],
            metadatas=[metadata] if metadata else [{"source": "manual"}],
            ids=[doc_id],
        )
        return f"✅ Belge vektörel hafızaya başarıyla eklendi (ID: {doc_id})."

    elif action == "search_memory":
        if not content:
            return "Aranacak sorgu belirtilmedi."
        results = collection.query(query_texts=[content], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        if not docs:
            return "Hafızada bu sorguyla eşleşen bir kayıt bulunamadı."
        response = "🔍 Vektörel Hafıza Sonuçları:\n"
        for i, doc in enumerate(docs, 1):
            response += f"\n[{i}] {doc[:300]}...\n"
        return response

    elif action == "list_collections":
        cols = client.list_collections()
        col_names = [c.name for c in cols] if cols else []
        return f"Mevcut Vektör Koleksiyonları: {', '.join(col_names) if col_names else 'Yok'}"

    return f"Bilinmeyen eylem: {action}"
