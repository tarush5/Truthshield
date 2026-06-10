"""
TruthShield — RAG Vector Store
Implements dense sentence embedding and TF-IDF fallback vector database for evidence retrieval.
"""
import logging
from typing import List, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


class RAGStore:
    """
    RAG (Retrieval-Augmented Generation) Vector Store.
    Implements document chunking, semantic indexing, and similarity retrieval.
    Falls back to TF-IDF vector space model if dense model loading fails,
    ensuring zero-config offline capability.
    """
    def __init__(self):
        self.documents = []
        self.vectorizer = None
        self.tfidf_matrix = None
        self.embeddings = None
        self.model = None
        self.tokenizer = None
        self._load_dense_model()

    def _load_dense_model(self):
        """Try to load a lightweight Transformer model for dense embeddings."""
        try:
            import torch
            from transformers import AutoTokenizer, AutoModel
            
            # Use a fast, small embedding model cached locally
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            logger.info("Dense sentence embeddings model loaded for RAG Store.")
        except Exception as e:
            logger.warning(f"Could not load dense embeddings model ({e}). Falling back to TF-IDF Vectorizer.")
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.vectorizer = TfidfVectorizer(stop_words='english')

    def add_documents(self, docs: List[Dict[str, Any]]):
        """
        Add documents to the vector store.
        Each doc should have 'text' and optional metadata ('title', 'url').
        """
        if not docs:
            return
        
        self.documents.extend(docs)
        texts = [doc.get("text", "") for doc in self.documents]
        
        if self.tokenizer and self.model:
            try:
                import torch
                # Compute embeddings using Mean Pooling
                self.embeddings = []
                for text in texts:
                    inputs = self.tokenizer(text, padding=True, truncation=True, max_length=256, return_tensors="pt")
                    with torch.no_grad():
                        outputs = self.model(**inputs)
                    # Mean pooling
                    token_embeddings = outputs[0]
                    input_mask_expanded = inputs['attention_mask'].unsqueeze(-1).expand(token_embeddings.size()).float()
                    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                    embedding = (sum_embeddings / sum_mask).numpy()[0]
                    # Normalize
                    embedding = embedding / np.linalg.norm(embedding)
                    self.embeddings.append(embedding)
                self.embeddings = np.array(self.embeddings)
            except Exception as e:
                logger.error(f"Error generating dense embeddings: {e}. Falling back to TF-IDF.")
                self.tokenizer = None
                self.model = None
                from sklearn.feature_extraction.text import TfidfVectorizer
                self.vectorizer = TfidfVectorizer(stop_words='english')
                self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        else:
            if self.vectorizer:
                try:
                    self.tfidf_matrix = self.vectorizer.fit_transform(texts)
                except Exception as e:
                    logger.warning(f"TF-IDF indexing failed: {e}")

    def query(self, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Query the vector store for the top_k most similar documents."""
        if not self.documents:
            return []
            
        if self.tokenizer and self.model and self.embeddings is not None:
            try:
                import torch
                # Generate query embedding
                inputs = self.tokenizer(query_text, padding=True, truncation=True, max_length=256, return_tensors="pt")
                with torch.no_grad():
                    outputs = self.model(**inputs)
                token_embeddings = outputs[0]
                input_mask_expanded = inputs['attention_mask'].unsqueeze(-1).expand(token_embeddings.size()).float()
                sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                query_emb = (sum_embeddings / sum_mask).numpy()[0]
                query_emb = query_emb / np.linalg.norm(query_emb)
                
                # Cosine similarity
                similarities = np.dot(self.embeddings, query_emb)
                top_indices = np.argsort(similarities)[::-1][:top_k]
                
                results = []
                for idx in top_indices:
                    doc = self.documents[idx].copy()
                    doc["similarity_score"] = float(similarities[idx])
                    results.append(doc)
                return results
            except Exception as e:
                logger.error(f"Dense query failed: {e}. Falling back to TF-IDF.")
                
        # TF-IDF Cosine Similarity fallback
        if self.vectorizer and self.tfidf_matrix is not None:
            try:
                from sklearn.metrics.pairwise import cosine_similarity
                query_vec = self.vectorizer.transform([query_text])
                similarities = cosine_similarity(self.tfidf_matrix, query_vec).flatten()
                top_indices = np.argsort(similarities)[::-1][:top_k]
                
                results = []
                for idx in top_indices:
                    # Skip 0 similarity if possible
                    if similarities[idx] <= 0 and len(results) > 0:
                        continue
                    doc = self.documents[idx].copy()
                    doc["similarity_score"] = float(similarities[idx])
                    results.append(doc)
                return results
            except Exception as e:
                logger.warning(f"TF-IDF query failed: {e}")
                
        # Simple string-matching/substring count fallback
        results = []
        for doc in self.documents:
            score = 0
            for word in query_text.lower().split():
                if word in doc.get("text", "").lower():
                    score += 1
            doc_copy = doc.copy()
            doc_copy["similarity_score"] = float(score)
            results.append(doc_copy)
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]
