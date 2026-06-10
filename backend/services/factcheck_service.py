"""
TruthShield — Fact Verification & pgvector RAG Service
"""
import uuid
import logging
import json
from typing import List, Dict, Any
import numpy as np
from sqlalchemy.orm import Session
from backend.models.db import DocumentChunk

logger = logging.getLogger(__name__)


class FactCheckService:
    """Service handling text embedding generation, document chunking, and pgvector RAG queries."""

    _tokenizer = None
    _model = None

    @classmethod
    def _initialize_model(cls):
        """Lazy-load the SentenceTransformer model."""
        if cls._model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModel
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            cls._tokenizer = AutoTokenizer.from_pretrained(model_name)
            cls._model = AutoModel.from_pretrained(model_name)
            logger.info("Sentence embeddings model loaded for FactCheck RAG Service.")
        except Exception as e:
            logger.warning(f"Could not load dense embeddings model in FactCheckService: {e}")

    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        """Generate a 384-dimensional normalized vector embedding for the input text."""
        cls._initialize_model()
        if cls._model is None or cls._tokenizer is None:
            # Deterministic hash-based mock embedding for robust offline execution
            import hashlib
            h = hashlib.md5(text.encode()).hexdigest()
            np.random.seed(int(h, 16) % (2**32 - 1))
            v = np.random.randn(384)
            v = v / np.linalg.norm(v)
            return v.tolist()
            
        import torch
        inputs = cls._tokenizer(text, padding=True, truncation=True, max_length=256, return_tensors="pt")
        with torch.no_grad():
            outputs = cls._model(**inputs)
        
        # Mean pooling
        token_embeddings = outputs[0]
        input_mask_expanded = inputs['attention_mask'].unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        embedding = (sum_embeddings / sum_mask).numpy()[0]
        
        # Normalize
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()

    @staticmethod
    def index_evidence(db: Session, text: str, metadata: dict) -> DocumentChunk:
        """Create embeddings and save document chunk to the vector database."""
        embedding = FactCheckService.generate_embedding(text)
        chunk = DocumentChunk(
            text=text,
            metadata_json=json.dumps(metadata),
            embedding=embedding
        )
        db.add(chunk)
        db.commit()
        db.refresh(chunk)
        logger.info("Document chunk successfully indexed in pgvector RAG database.")
        return chunk

    @staticmethod
    def query_evidence(db: Session, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Perform semantic search using pgvector (PostgreSQL) or numpy similarity fallback (SQLite)."""
        query_vector = FactCheckService.generate_embedding(query_text)
        
        # Determine engine dialect
        driver = db.bind.url.drivername
        is_postgres = "postgresql" in driver
        
        if is_postgres:
            try:
                from sqlalchemy import text
                # Convert query vector list to postgres vector format string: '[v1,v2,...]'
                vector_str = "[" + ",".join(map(str, query_vector)) + "]"
                
                # Execute native cosine distance query using pgvector <=> operator
                sql_query = text(
                    "SELECT id, text, metadata_json, (embedding <=> :vector) as distance "
                    "FROM document_chunks ORDER BY distance LIMIT :limit"
                )
                results = db.execute(sql_query, {"vector": vector_str, "limit": top_k}).all()
                
                docs = []
                for row in results:
                    docs.append({
                        "id": str(row[0]),
                        "text": row[1],
                        "metadata": json.loads(row[2]) if row[2] else {},
                        "distance": float(row[3]),
                        "similarity_score": round(1.0 - float(row[3]), 4)
                    })
                logger.info(f"Retrieved {len(docs)} documents using native pgvector search.")
                return docs
            except Exception as e:
                logger.warning(f"Native pgvector search failed: {e}. Falling back to memory-based query.")
                
        # Memory-based cosine similarity fallback (SQLite)
        chunks = db.query(DocumentChunk).all()
        if not chunks:
            return []
            
        similarities = []
        for chunk in chunks:
            emb = chunk.embedding
            # If SQLite stored it as a JSON string, decode it
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    continue
            if emb:
                # Cosine similarity of normalized vectors is their dot product
                similarity = np.dot(emb, query_vector)
                similarities.append((chunk, similarity))
                
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        docs = []
        for chunk, score in similarities[:top_k]:
            docs.append({
                "id": str(chunk.id),
                "text": chunk.text,
                "metadata": json.loads(chunk.metadata_json) if chunk.metadata_json else {},
                "similarity_score": round(float(score), 4)
            })
        logger.info(f"Retrieved {len(docs)} documents using fallback semantic search.")
        return docs
