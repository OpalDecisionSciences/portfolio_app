"""
Hybrid retrieval system combining dense (vector) and sparse (BM25) retrieval methods.
"""
import logging
import pickle
import os
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import re

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from langchain_core.documents import Document
from langchain_postgres import PGVector

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')


class HybridRetriever:
    """
    Hybrid retrieval system combining dense vector search with sparse BM25 retrieval.
    Uses Reciprocal Rank Fusion (RRF) to combine results from both methods.
    """
    
    def __init__(
        self, 
        vector_store: PGVector,
        bm25_index_path: Optional[str] = None,
        alpha: float = 0.7,
        k1: float = 1.2,
        b: float = 0.75
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            vector_store: LangChain PGVector store for dense retrieval
            bm25_index_path: Path to save/load BM25 index
            alpha: Weight for dense vs sparse (0.7 = 70% dense, 30% sparse)
            k1: BM25 term frequency saturation parameter
            b: BM25 field length normalization parameter
        """
        self.vector_store = vector_store
        self.alpha = alpha
        self.k1 = k1
        self.b = b
        
        # Initialize text processing
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        
        # BM25 components
        self.bm25_index = None
        self.documents = []
        self.doc_metadata = []
        self.bm25_index_path = bm25_index_path or "/app/data/bm25_index.pkl"
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.bm25_index_path), exist_ok=True)
        
        # Load existing BM25 index if available
        self._load_bm25_index()
    
    def preprocess_text(self, text: str) -> List[str]:
        """
        Preprocess text for BM25 indexing.
        
        Args:
            text: Raw text to preprocess
            
        Returns:
            List of processed tokens
        """
        # Convert to lowercase and remove special characters
        text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
        
        # Tokenize
        tokens = word_tokenize(text)
        
        # Remove stopwords and stem
        processed_tokens = [
            self.stemmer.stem(token) 
            for token in tokens 
            if token not in self.stop_words and len(token) > 2
        ]
        
        return processed_tokens
    
    def build_bm25_index(self, documents: List[Document]) -> None:
        """
        Build BM25 index from documents.
        
        Args:
            documents: List of LangChain documents
        """
        logger.info(f"Building BM25 index with {len(documents)} documents")
        
        # Process documents for BM25
        processed_docs = []
        self.documents = []
        self.doc_metadata = []
        
        for doc in documents:
            processed_text = self.preprocess_text(doc.page_content)
            processed_docs.append(processed_text)
            self.documents.append(doc.page_content)
            self.doc_metadata.append(doc.metadata)
        
        # Create BM25 index
        self.bm25_index = BM25Okapi(processed_docs, k1=self.k1, b=self.b)
        
        # Save index
        self._save_bm25_index()
        
        logger.info("BM25 index built and saved successfully")
    
    def _save_bm25_index(self) -> None:
        """Save BM25 index to disk."""
        try:
            index_data = {
                'bm25_index': self.bm25_index,
                'documents': self.documents,
                'doc_metadata': self.doc_metadata
            }
            
            with open(self.bm25_index_path, 'wb') as f:
                pickle.dump(index_data, f)
                
            logger.info(f"BM25 index saved to {self.bm25_index_path}")
            
        except Exception as e:
            logger.error(f"Error saving BM25 index: {str(e)}")
    
    def _load_bm25_index(self) -> None:
        """Load BM25 index from disk."""
        try:
            if os.path.exists(self.bm25_index_path):
                with open(self.bm25_index_path, 'rb') as f:
                    index_data = pickle.load(f)
                
                self.bm25_index = index_data['bm25_index']
                self.documents = index_data['documents']
                self.doc_metadata = index_data['doc_metadata']
                
                logger.info(f"BM25 index loaded from {self.bm25_index_path}")
            else:
                logger.info("No existing BM25 index found")
                
        except Exception as e:
            logger.error(f"Error loading BM25 index: {str(e)}")
            self.bm25_index = None
    
    def bm25_search(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """
        Perform BM25 sparse retrieval.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of (document, score) tuples
        """
        if self.bm25_index is None:
            logger.warning("BM25 index not available")
            return []
        
        # Preprocess query
        processed_query = self.preprocess_text(query)
        
        if not processed_query:
            return []
        
        # Get BM25 scores
        scores = self.bm25_index.get_scores(processed_query)
        
        # Get top-k results
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include positive scores
                doc = Document(
                    page_content=self.documents[idx],
                    metadata=self.doc_metadata[idx]
                )
                results.append((doc, float(scores[idx])))
        
        return results
    
    def reciprocal_rank_fusion(
        self, 
        dense_results: List[Tuple[Document, float]], 
        sparse_results: List[Tuple[Document, float]], 
        k: int = 10,
        rrf_k: int = 60
    ) -> List[Tuple[Document, float]]:
        """
        Combine dense and sparse results using Reciprocal Rank Fusion.
        
        Args:
            dense_results: Results from vector search
            sparse_results: Results from BM25 search
            k: Number of final results to return
            rrf_k: RRF parameter (typically 60)
            
        Returns:
            Fused and ranked results
        """
        # Create document to score mapping
        doc_scores = {}
        
        # Add dense results
        for rank, (doc, score) in enumerate(dense_results):
            doc_key = doc.page_content[:100]  # Use first 100 chars as key
            rrf_score = self.alpha / (rrf_k + rank + 1)
            doc_scores[doc_key] = {
                'document': doc,
                'score': rrf_score,
                'dense_rank': rank + 1,
                'sparse_rank': None
            }
        
        # Add sparse results
        for rank, (doc, score) in enumerate(sparse_results):
            doc_key = doc.page_content[:100]
            rrf_score = (1 - self.alpha) / (rrf_k + rank + 1)
            
            if doc_key in doc_scores:
                # Document found in both - combine scores
                doc_scores[doc_key]['score'] += rrf_score
                doc_scores[doc_key]['sparse_rank'] = rank + 1
            else:
                # Document only in sparse results
                doc_scores[doc_key] = {
                    'document': doc,
                    'score': rrf_score,
                    'dense_rank': None,
                    'sparse_rank': rank + 1
                }
        
        # Sort by combined score and return top-k
        sorted_results = sorted(
            doc_scores.values(), 
            key=lambda x: x['score'], 
            reverse=True
        )[:k]
        
        return [(item['document'], item['score']) for item in sorted_results]
    
    def hybrid_search(
        self, 
        query: str, 
        k: int = 10,
        dense_k: int = 20,
        sparse_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        """
        Perform hybrid search combining dense and sparse retrieval.
        
        Args:
            query: Search query
            k: Number of final results to return
            dense_k: Number of results from dense search
            sparse_k: Number of results from sparse search
            filters: Optional metadata filters for dense search
            
        Returns:
            Hybrid search results
        """
        logger.info(f"Performing hybrid search for query: {query[:50]}...")
        
        # Dense retrieval (vector search)
        try:
            if filters:
                dense_docs = self.vector_store.similarity_search_with_score(
                    query, k=dense_k, filter=filters
                )
            else:
                dense_docs = self.vector_store.similarity_search_with_score(
                    query, k=dense_k
                )
            logger.info(f"Dense search returned {len(dense_docs)} results")
        except Exception as e:
            logger.error(f"Error in dense search: {str(e)}")
            dense_docs = []
        
        # Sparse retrieval (BM25)
        try:
            sparse_docs = self.bm25_search(query, k=sparse_k)
            logger.info(f"Sparse search returned {len(sparse_docs)} results")
        except Exception as e:
            logger.error(f"Error in sparse search: {str(e)}")
            sparse_docs = []
        
        # Combine using RRF
        if dense_docs or sparse_docs:
            hybrid_results = self.reciprocal_rank_fusion(dense_docs, sparse_docs, k)
            logger.info(f"Hybrid fusion returned {len(hybrid_results)} results")
            return hybrid_results
        else:
            logger.warning("No results from either dense or sparse search")
            return []
    
    def get_relevant_documents(self, query: str, k: int = 5) -> List[Document]:
        """
        Get relevant documents (compatible with LangChain retriever interface).
        
        Args:
            query: Search query
            k: Number of documents to return
            
        Returns:
            List of relevant documents
        """
        results = self.hybrid_search(query, k=k)
        return [doc for doc, score in results]
    
    def rebuild_index(self) -> None:
        """Rebuild BM25 index from current vector store."""
        try:
            # Get all documents from vector store
            all_docs = self.vector_store.similarity_search("", k=10000)  # Large k to get all
            
            if all_docs:
                self.build_bm25_index(all_docs)
                logger.info(f"Rebuilt BM25 index with {len(all_docs)} documents")
            else:
                logger.warning("No documents found in vector store for index rebuild")
                
        except Exception as e:
            logger.error(f"Error rebuilding BM25 index: {str(e)}")
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the hybrid retrieval system."""
        stats = {
            'alpha': self.alpha,
            'bm25_available': self.bm25_index is not None,
            'vector_store_available': self.vector_store is not None,
            'total_documents': len(self.documents) if self.documents else 0,
            'index_path': self.bm25_index_path,
            'index_exists': os.path.exists(self.bm25_index_path)
        }
        
        return stats