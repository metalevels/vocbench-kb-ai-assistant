"""
Vector database interface using ChromaDB
"""
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    """Interface for vector database operations using ChromaDB"""

    def __init__(
        self,
        collection_name: str = "vocbench_knowledge",
        persist_directory: str = "./data/chromadb",
        host: Optional[str] = None,
        port: Optional[int] = None
    ):
        """
        Initialize vector store

        Args:
            collection_name: Name of the collection
            persist_directory: Directory for persistent storage (local mode)
            host: ChromaDB server host (client mode)
            port: ChromaDB server port (client mode)
        """
        self.collection_name = collection_name

        # Initialize ChromaDB client
        if host and port:
            # Client mode (connect to server)
            logger.info(f"Connecting to ChromaDB server at {host}:{port}")
            self.client = chromadb.HttpClient(host=host, port=port)
        else:
            # Local mode (persistent)
            logger.info(f"Using local ChromaDB with persistence at {persist_directory}")
            self.client = chromadb.PersistentClient(path=persist_directory)

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "VocBench Google Group knowledge base"}
        )

        logger.info(f"Vector store initialized with collection '{collection_name}'")

    def add_documents(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> int:
        """
        Add documents to the vector store

        Args:
            documents: List of document texts
            embeddings: List of embedding vectors
            metadatas: List of metadata dicts
            ids: Optional list of document IDs (auto-generated if None)

        Returns:
            Number of documents added
        """
        if not documents:
            logger.warning("No documents to add")
            return 0

        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]

        # Ensure all lists have the same length
        assert len(documents) == len(embeddings) == len(metadatas) == len(ids), \
            "All input lists must have the same length"

        logger.info(f"Adding {len(documents)} documents to collection '{self.collection_name}'")

        # Add to ChromaDB
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Successfully added {len(documents)} documents")
        return len(documents)

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Search for similar documents

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Metadata filter (e.g., {"thread_id": "thread_123"})
            where_document: Document content filter

        Returns:
            Search results with ids, documents, metadatas, and distances
        """
        logger.debug(f"Searching for {n_results} similar documents")

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document
        )

        # Format results
        formatted_results = {
            'ids': results['ids'][0] if results['ids'] else [],
            'documents': results['documents'][0] if results['documents'] else [],
            'metadatas': results['metadatas'][0] if results['metadatas'] else [],
            'distances': results['distances'][0] if results['distances'] else []
        }

        logger.debug(f"Found {len(formatted_results['ids'])} results")
        return formatted_results

    def batch_search(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple queries at once

        Args:
            query_embeddings: List of query embedding vectors
            n_results: Number of results per query
            where: Metadata filter

        Returns:
            List of search results
        """
        logger.info(f"Batch searching {len(query_embeddings)} queries")

        results = self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where
        )

        # Format results for each query
        formatted_results = []
        for i in range(len(query_embeddings)):
            formatted_results.append({
                'ids': results['ids'][i],
                'documents': results['documents'][i],
                'metadatas': results['metadatas'][i],
                'distances': results['distances'][i]
            })

        return formatted_results

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific document by ID

        Args:
            doc_id: Document ID

        Returns:
            Document data or None if not found
        """
        try:
            result = self.collection.get(ids=[doc_id])
            if result['ids']:
                return {
                    'id': result['ids'][0],
                    'document': result['documents'][0],
                    'metadata': result['metadatas'][0]
                }
            return None
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {e}")
            return None

    def update_document(
        self,
        doc_id: str,
        document: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Update an existing document

        Args:
            doc_id: Document ID to update
            document: New document text (optional)
            embedding: New embedding vector (optional)
            metadata: New metadata (optional)
        """
        logger.info(f"Updating document {doc_id}")

        update_data = {'ids': [doc_id]}
        if document is not None:
            update_data['documents'] = [document]
        if embedding is not None:
            update_data['embeddings'] = [embedding]
        if metadata is not None:
            update_data['metadatas'] = [metadata]

        self.collection.update(**update_data)
        logger.info(f"Document {doc_id} updated")

    def delete_documents(self, doc_ids: List[str]):
        """
        Delete documents by IDs

        Args:
            doc_ids: List of document IDs to delete
        """
        logger.info(f"Deleting {len(doc_ids)} documents")
        self.collection.delete(ids=doc_ids)
        logger.info(f"Deleted {len(doc_ids)} documents")

    def delete_collection(self):
        """Delete the entire collection"""
        logger.warning(f"Deleting collection '{self.collection_name}'")
        self.client.delete_collection(name=self.collection_name)
        logger.info(f"Collection '{self.collection_name}' deleted")

    def count(self) -> int:
        """
        Get number of documents in the collection

        Returns:
            Number of documents
        """
        count = self.collection.count()
        logger.debug(f"Collection has {count} documents")
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get collection statistics

        Returns:
            Dictionary of statistics
        """
        count = self.count()

        stats = {
            'collection_name': self.collection_name,
            'total_documents': count,
            'metadata': self.collection.metadata
        }

        return stats

    def clear(self):
        """Clear all documents from the collection"""
        logger.warning(f"Clearing all documents from collection '{self.collection_name}'")

        # Get all document IDs
        all_docs = self.collection.get()
        if all_docs['ids']:
            self.delete_documents(all_docs['ids'])
            logger.info(f"Cleared {len(all_docs['ids'])} documents")
        else:
            logger.info("Collection already empty")


class VectorStoreManager:
    """Manager for handling multiple vector stores and indexing operations"""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize manager

        Args:
            vector_store: VectorStore instance
        """
        self.vector_store = vector_store

    def index_processed_data(
        self,
        processed_data: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """
        Index processed data into vector store

        Args:
            processed_data: List of processed chunks with embeddings
            batch_size: Batch size for indexing

        Returns:
            Total number of documents indexed
        """
        total_indexed = 0

        logger.info(f"Indexing {len(processed_data)} chunks in batches of {batch_size}")

        for i in range(0, len(processed_data), batch_size):
            batch = processed_data[i:i + batch_size]

            ids = [chunk['chunk_id'] for chunk in batch]
            documents = [chunk['content'] for chunk in batch]
            embeddings = [chunk['embedding'] for chunk in batch]
            metadatas = [chunk['metadata'] for chunk in batch]

            count = self.vector_store.add_documents(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )

            total_indexed += count
            logger.info(f"Indexed batch {i // batch_size + 1}: {count} documents")

        logger.info(f"Total indexed: {total_indexed} documents")
        return total_indexed

    def reindex(self, processed_data: List[Dict[str, Any]]):
        """
        Clear and reindex all data

        Args:
            processed_data: List of processed chunks with embeddings
        """
        logger.info("Reindexing: clearing existing data")
        self.vector_store.clear()

        logger.info("Reindexing: adding new data")
        return self.index_processed_data(processed_data)
