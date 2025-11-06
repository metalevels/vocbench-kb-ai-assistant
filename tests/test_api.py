"""
Tests for the API module
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

# We'll mock the dependencies during import
with patch('src.api.main.VectorStore'), \
     patch('src.api.main.EmbeddingGenerator'), \
     patch('src.api.main.SemanticRetriever'), \
     patch('src.api.main.VocBenchAssistant'), \
     patch('src.api.main.ConversationManager'):
    from src.api.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_assistant_response():
    """Mock assistant response"""
    return {
        'response': 'Here is how to configure SPARQL...',
        'sources': [
            {
                'id': 'doc_1',
                'content': 'SPARQL configuration guide',
                'score': 0.95,
                'metadata': {'subject': 'SPARQL Config'}
            }
        ],
        'usage': {'input_tokens': 100, 'output_tokens': 50}
    }


class TestRootEndpoint:
    """Test root endpoint"""

    def test_root(self, client):
        """Test root endpoint returns API info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "VocBench" in data["message"]


class TestChatEndpoint:
    """Test chat endpoint"""

    def test_chat_request_validation(self, client):
        """Test chat request validation"""
        # Empty message should fail
        response = client.post(
            "/chat",
            json={"message": "", "top_k": 5}
        )
        assert response.status_code == 422  # Validation error

    def test_chat_success(self, client, mock_assistant_response):
        """Test successful chat request"""
        with patch('src.api.main.assistant') as mock_assistant, \
             patch('src.api.main.conversation_manager') as mock_conv_mgr:

            mock_assistant.chat.return_value = mock_assistant_response

            response = client.post(
                "/chat",
                json={
                    "message": "How to configure SPARQL?",
                    "top_k": 5,
                    "include_sources": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "sources" in data
            assert len(data["sources"]) > 0


class TestSearchEndpoint:
    """Test search endpoint"""

    def test_search_request_validation(self, client):
        """Test search request validation"""
        # Empty query should fail
        response = client.post(
            "/search",
            json={"query": ""}
        )
        assert response.status_code == 422

    def test_search_success(self, client):
        """Test successful search request"""
        mock_results = [
            {
                'id': 'doc_1',
                'content': 'Test content',
                'score': 0.9,
                'metadata': {}
            }
        ]

        with patch('src.api.main.retriever') as mock_retriever:
            mock_retriever.retrieve.return_value = mock_results

            response = client.post(
                "/search",
                json={
                    "query": "test query",
                    "top_k": 10
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert data["total_results"] > 0


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Test health check endpoint"""
        with patch('src.api.main.vector_store') as mock_vs:
            mock_vs.count.return_value = 100

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "total_documents" in data


class TestStatsEndpoint:
    """Test statistics endpoint"""

    def test_stats(self, client):
        """Test stats endpoint"""
        mock_stats = {
            'total_documents': 100,
            'collection_name': 'test_collection'
        }

        with patch('src.api.main.vector_store') as mock_vs:
            mock_vs.get_statistics.return_value = mock_stats

            response = client.get("/stats")
            assert response.status_code == 200
            data = response.json()
            assert "total_documents" in data
            assert "embedding_model" in data
