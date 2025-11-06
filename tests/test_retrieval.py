"""
Tests for the retrieval module
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from src.retrieval.vector_store import VectorStore, VectorStoreManager
from src.processor.embeddings import EmbeddingGenerator


class TestVectorStore:
    """Test vector store functionality"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def vector_store(self, temp_db):
        """Create vector store instance"""
        return VectorStore(
            collection_name="test_collection",
            persist_directory=temp_db
        )

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        return {
            'documents': [
                "How to configure SPARQL endpoint in VocBench?",
                "Error importing SKOS vocabulary",
                "Best practices for collaborative editing"
            ],
            'embeddings': [
                [0.1] * 384,  # Mock embeddings
                [0.2] * 384,
                [0.3] * 384
            ],
            'metadatas': [
                {"thread_id": "thread_1", "author": "John"},
                {"thread_id": "thread_2", "author": "Jane"},
                {"thread_id": "thread_3", "author": "Bob"}
            ],
            'ids': ["doc_1", "doc_2", "doc_3"]
        }

    def test_add_documents(self, vector_store, sample_data):
        """Test adding documents to vector store"""
        count = vector_store.add_documents(
            documents=sample_data['documents'],
            embeddings=sample_data['embeddings'],
            metadatas=sample_data['metadatas'],
            ids=sample_data['ids']
        )

        assert count == 3
        assert vector_store.count() == 3

    def test_search(self, vector_store, sample_data):
        """Test searching for similar documents"""
        # Add documents
        vector_store.add_documents(
            documents=sample_data['documents'],
            embeddings=sample_data['embeddings'],
            metadatas=sample_data['metadatas'],
            ids=sample_data['ids']
        )

        # Search with query embedding
        query_embedding = [0.15] * 384  # Should be close to first doc
        results = vector_store.search(
            query_embedding=query_embedding,
            n_results=2
        )

        assert len(results['ids']) <= 2
        assert len(results['documents']) == len(results['ids'])
        assert len(results['metadatas']) == len(results['ids'])

    def test_get_document(self, vector_store, sample_data):
        """Test retrieving a specific document"""
        vector_store.add_documents(
            documents=sample_data['documents'],
            embeddings=sample_data['embeddings'],
            metadatas=sample_data['metadatas'],
            ids=sample_data['ids']
        )

        doc = vector_store.get_document("doc_1")
        assert doc is not None
        assert doc['id'] == "doc_1"
        assert "SPARQL" in doc['document']

    def test_update_document(self, vector_store, sample_data):
        """Test updating a document"""
        vector_store.add_documents(
            documents=sample_data['documents'],
            embeddings=sample_data['embeddings'],
            metadatas=sample_data['metadatas'],
            ids=sample_data['ids']
        )

        # Update document
        new_metadata = {"thread_id": "thread_1", "author": "John", "updated": True}
        vector_store.update_document(
            doc_id="doc_1",
            metadata=new_metadata
        )

        # Verify update
        doc = vector_store.get_document("doc_1")
        assert doc['metadata']['updated'] is True

    def test_delete_documents(self, vector_store, sample_data):
        """Test deleting documents"""
        vector_store.add_documents(
            documents=sample_data['documents'],
            embeddings=sample_data['embeddings'],
            metadatas=sample_data['metadatas'],
            ids=sample_data['ids']
        )

        initial_count = vector_store.count()
        vector_store.delete_documents(["doc_1", "doc_2"])

        assert vector_store.count() == initial_count - 2

    def test_clear(self, vector_store, sample_data):
        """Test clearing all documents"""
        vector_store.add_documents(
            documents=sample_data['documents'],
            embeddings=sample_data['embeddings'],
            metadatas=sample_data['metadatas'],
            ids=sample_data['ids']
        )

        assert vector_store.count() > 0
        vector_store.clear()
        assert vector_store.count() == 0

    def test_get_statistics(self, vector_store, sample_data):
        """Test getting collection statistics"""
        vector_store.add_documents(
            documents=sample_data['documents'],
            embeddings=sample_data['embeddings'],
            metadatas=sample_data['metadatas'],
            ids=sample_data['ids']
        )

        stats = vector_store.get_statistics()
        assert stats['total_documents'] == 3
        assert stats['collection_name'] == "test_collection"


class TestVectorStoreManager:
    """Test vector store manager"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def manager(self, temp_db):
        """Create manager instance"""
        vector_store = VectorStore(
            collection_name="test_manager",
            persist_directory=temp_db
        )
        return VectorStoreManager(vector_store)

    @pytest.fixture
    def processed_data(self):
        """Create sample processed data"""
        return [
            {
                'chunk_id': 'msg_1_chunk_0',
                'source_id': 'msg_1',
                'chunk_index': 0,
                'content': 'How to configure SPARQL?',
                'embedding': [0.1] * 384,
                'metadata': {'thread_id': 'thread_1'}
            },
            {
                'chunk_id': 'msg_2_chunk_0',
                'source_id': 'msg_2',
                'chunk_index': 0,
                'content': 'Error importing SKOS',
                'embedding': [0.2] * 384,
                'metadata': {'thread_id': 'thread_2'}
            }
        ]

    def test_index_processed_data(self, manager, processed_data):
        """Test indexing processed data"""
        count = manager.index_processed_data(processed_data, batch_size=10)
        assert count == 2
        assert manager.vector_store.count() == 2

    def test_reindex(self, manager, processed_data):
        """Test reindexing"""
        # Initial index
        manager.index_processed_data(processed_data)
        assert manager.vector_store.count() == 2

        # Reindex with new data
        new_data = processed_data + [
            {
                'chunk_id': 'msg_3_chunk_0',
                'source_id': 'msg_3',
                'chunk_index': 0,
                'content': 'Collaborative editing tips',
                'embedding': [0.3] * 384,
                'metadata': {'thread_id': 'thread_3'}
            }
        ]
        count = manager.reindex(new_data)
        assert count == 3
        assert manager.vector_store.count() == 3


@pytest.fixture
def embedding_generator():
    """Create embedding generator for tests"""
    return EmbeddingGenerator(model_name="all-MiniLM-L6-v2")
