"""
Semantic retrieval and ranking layer
"""
import logging
from typing import List, Dict, Any, Optional
import numpy as np

from src.retrieval.vector_store import VectorStore
from src.processor.embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """Retrieves relevant documents using semantic search"""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        default_top_k: int = 5
    ):
        """
        Initialize retriever

        Args:
            vector_store: VectorStore instance
            embedding_generator: EmbeddingGenerator instance
            default_top_k: Default number of results to return
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.default_top_k = default_top_k

        logger.info("SemanticRetriever initialized")

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        min_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query

        Args:
            query: Query string
            top_k: Number of results to return (uses default if None)
            filters: Metadata filters
            min_score: Minimum similarity score threshold

        Returns:
            List of retrieved documents with scores
        """
        if not query or not query.strip():
            logger.warning("Empty query provided")
            return []

        k = top_k or self.default_top_k

        # Generate query embedding
        logger.debug(f"Generating embedding for query: {query[:100]}...")
        query_embedding = self.embedding_generator.generate_embedding(query)

        # Search vector store
        logger.debug(f"Searching for top {k} results")
        results = self.vector_store.search(
            query_embedding=query_embedding.tolist(),
            n_results=k,
            where=filters
        )

        # Format results
        retrieved_docs = []
        for i, doc_id in enumerate(results['ids']):
            # Convert distance to similarity score (1 - normalized distance)
            # Note: ChromaDB uses L2 distance by default
            distance = results['distances'][i]
            similarity_score = 1.0 / (1.0 + distance)  # Convert to similarity

            # Apply minimum score filter if specified
            if min_score is not None and similarity_score < min_score:
                continue

            retrieved_docs.append({
                'id': doc_id,
                'content': results['documents'][i],
                'metadata': results['metadatas'][i],
                'score': similarity_score,
                'distance': distance
            })

        logger.info(f"Retrieved {len(retrieved_docs)} documents for query")
        return retrieved_docs

    def batch_retrieve(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Retrieve documents for multiple queries

        Args:
            queries: List of query strings
            top_k: Number of results per query
            filters: Metadata filters

        Returns:
            List of result lists (one per query)
        """
        logger.info(f"Batch retrieving for {len(queries)} queries")

        # Generate embeddings for all queries
        query_embeddings = self.embedding_generator.generate_embeddings(
            queries,
            show_progress=False
        )

        # Batch search
        k = top_k or self.default_top_k
        batch_results = self.vector_store.batch_search(
            query_embeddings=[emb.tolist() for emb in query_embeddings],
            n_results=k,
            where=filters
        )

        # Format results
        all_retrieved = []
        for results in batch_results:
            retrieved_docs = []
            for i, doc_id in enumerate(results['ids']):
                distance = results['distances'][i]
                similarity_score = 1.0 / (1.0 + distance)

                retrieved_docs.append({
                    'id': doc_id,
                    'content': results['documents'][i],
                    'metadata': results['metadatas'][i],
                    'score': similarity_score,
                    'distance': distance
                })
            all_retrieved.append(retrieved_docs)

        return all_retrieved

    def retrieve_with_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        context_window: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents with surrounding context chunks

        Args:
            query: Query string
            top_k: Number of results to return
            context_window: Number of adjacent chunks to include

        Returns:
            List of retrieved documents with context
        """
        # First, retrieve the most relevant chunks
        results = self.retrieve(query, top_k)

        if context_window == 0:
            return results

        # For each result, try to get adjacent chunks
        results_with_context = []
        for result in results:
            # Extract source_id and chunk_index from metadata
            source_id = result['metadata'].get('source_id')
            chunk_index = result['metadata'].get('chunk_index')

            if source_id is None or chunk_index is None:
                results_with_context.append(result)
                continue

            # Try to get surrounding chunks
            context_chunks = [result]  # Include the original chunk

            # Get previous and next chunks
            for offset in range(1, context_window + 1):
                # Previous chunk
                prev_id = f"{source_id}_chunk_{chunk_index - offset}"
                prev_chunk = self.vector_store.get_document(prev_id)
                if prev_chunk:
                    context_chunks.insert(0, {
                        'id': prev_chunk['id'],
                        'content': prev_chunk['document'],
                        'metadata': prev_chunk['metadata'],
                        'is_context': True
                    })

                # Next chunk
                next_id = f"{source_id}_chunk_{chunk_index + offset}"
                next_chunk = self.vector_store.get_document(next_id)
                if next_chunk:
                    context_chunks.append({
                        'id': next_chunk['id'],
                        'content': next_chunk['document'],
                        'metadata': next_chunk['metadata'],
                        'is_context': True
                    })

            # Combine context chunks
            combined_content = "\n\n".join([c['content'] for c in context_chunks])
            result['content_with_context'] = combined_content
            result['context_chunks'] = context_chunks

            results_with_context.append(result)

        return results_with_context

    def hybrid_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword matching

        Args:
            query: Query string
            top_k: Number of results to return
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)

        Returns:
            List of retrieved documents with hybrid scores
        """
        k = top_k or self.default_top_k

        # Semantic search
        semantic_results = self.retrieve(query, top_k=k * 2)  # Get more for reranking

        # Simple keyword-based scoring (count of matching terms)
        query_terms = set(query.lower().split())

        for result in semantic_results:
            content_terms = set(result['content'].lower().split())
            keyword_matches = len(query_terms.intersection(content_terms))
            keyword_score = min(keyword_matches / len(query_terms), 1.0) if query_terms else 0.0

            # Combine scores
            hybrid_score = (
                semantic_weight * result['score'] +
                keyword_weight * keyword_score
            )
            result['hybrid_score'] = hybrid_score
            result['keyword_score'] = keyword_score

        # Re-rank by hybrid score
        semantic_results.sort(key=lambda x: x['hybrid_score'], reverse=True)

        return semantic_results[:k]


class RetrievalResult:
    """Container for retrieval results with formatting utilities"""

    def __init__(self, results: List[Dict[str, Any]], query: str):
        """
        Initialize result container

        Args:
            results: List of retrieved documents
            query: Original query
        """
        self.results = results
        self.query = query

    def format_for_llm(self, max_chunks: int = 5, include_metadata: bool = True) -> str:
        """
        Format results for LLM context

        Args:
            max_chunks: Maximum number of chunks to include
            include_metadata: Include metadata in formatting

        Returns:
            Formatted string for LLM context
        """
        if not self.results:
            return "No relevant information found."

        context_parts = [f"Query: {self.query}\n\nRelevant information:\n"]

        for i, result in enumerate(self.results[:max_chunks], 1):
            context_parts.append(f"\n[Source {i}]")

            if include_metadata and result.get('metadata'):
                meta = result['metadata']
                if meta.get('subject'):
                    context_parts.append(f"Subject: {meta['subject']}")
                if meta.get('author'):
                    context_parts.append(f"Author: {meta['author']}")
                if meta.get('date'):
                    context_parts.append(f"Date: {meta['date']}")

            context_parts.append(f"\n{result['content']}\n")

        return "\n".join(context_parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'query': self.query,
            'num_results': len(self.results),
            'results': self.results
        }
