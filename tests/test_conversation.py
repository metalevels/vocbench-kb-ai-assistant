"""
Tests for the conversation module
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

from src.conversation.chat import VocBenchAssistant, ConversationManager


class TestVocBenchAssistant:
    """Test VocBench assistant"""

    @pytest.fixture
    def mock_retriever(self):
        """Create mock retriever"""
        retriever = Mock()
        retriever.retrieve.return_value = [
            {
                'id': 'doc_1',
                'content': 'To configure SPARQL endpoint, go to Settings.',
                'metadata': {'subject': 'SPARQL Config', 'author': 'John'},
                'score': 0.9
            }
        ]
        return retriever

    @pytest.fixture
    def mock_anthropic_response(self):
        """Create mock Anthropic response"""
        response = Mock()
        response.content = [Mock(text="Here's how to configure SPARQL in VocBench...")]
        response.usage = Mock(input_tokens=100, output_tokens=50)
        return response

    def test_assistant_initialization(self, mock_retriever):
        """Test assistant initialization"""
        with patch('src.conversation.chat.Anthropic'):
            assistant = VocBenchAssistant(
                retriever=mock_retriever,
                api_key="test_key"
            )
            assert assistant.retriever == mock_retriever
            assert assistant.model == "claude-3-5-sonnet-20241022"

    def test_chat_empty_message(self, mock_retriever):
        """Test handling of empty message"""
        with patch('src.conversation.chat.Anthropic'):
            assistant = VocBenchAssistant(
                retriever=mock_retriever,
                api_key="test_key"
            )
            result = assistant.chat("")
            assert 'error' in result
            assert 'Empty message' in result['error']

    def test_chat_with_context(self, mock_retriever, mock_anthropic_response):
        """Test chat with retrieved context"""
        with patch('src.conversation.chat.Anthropic') as mock_anthropic_class:
            # Setup mock
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic_class.return_value = mock_client

            assistant = VocBenchAssistant(
                retriever=mock_retriever,
                api_key="test_key"
            )

            result = assistant.chat("How to configure SPARQL?", top_k=3)

            # Verify retrieval was called
            mock_retriever.retrieve.assert_called_once()

            # Verify API was called
            mock_client.messages.create.assert_called_once()

            # Check result structure
            assert 'response' in result
            assert 'sources' in result
            assert 'usage' in result

    def test_default_system_prompt(self, mock_retriever):
        """Test default system prompt"""
        with patch('src.conversation.chat.Anthropic'):
            assistant = VocBenchAssistant(
                retriever=mock_retriever,
                api_key="test_key"
            )
            prompt = assistant._get_default_system_prompt()
            assert "VocBench" in prompt
            assert "SKOS" in prompt


class TestConversationManager:
    """Test conversation manager"""

    @pytest.fixture
    def mock_assistant(self):
        """Create mock assistant"""
        assistant = Mock()
        assistant.chat.return_value = {
            'response': 'Test response',
            'sources': [],
            'usage': {'input_tokens': 50, 'output_tokens': 25}
        }
        return assistant

    @pytest.fixture
    def manager(self, mock_assistant):
        """Create conversation manager"""
        return ConversationManager(mock_assistant, max_history=5)

    def test_start_conversation(self, manager):
        """Test starting a conversation"""
        manager.start_conversation("conv_1")
        assert "conv_1" in manager.conversations
        assert len(manager.conversations["conv_1"]) == 0

    def test_send_message(self, manager, mock_assistant):
        """Test sending a message"""
        result = manager.send_message("conv_1", "Hello")

        # Verify assistant was called
        mock_assistant.chat.assert_called_once()

        # Verify history was updated
        assert len(manager.conversations["conv_1"]) == 2  # user + assistant
        assert manager.conversations["conv_1"][0]['role'] == 'user'
        assert manager.conversations["conv_1"][1]['role'] == 'assistant'

    def test_get_history(self, manager):
        """Test getting conversation history"""
        manager.start_conversation("conv_1")
        manager.send_message("conv_1", "Message 1")
        manager.send_message("conv_1", "Message 2")

        history = manager.get_history("conv_1")
        assert len(history) == 4  # 2 user + 2 assistant

    def test_clear_conversation(self, manager):
        """Test clearing a conversation"""
        manager.start_conversation("conv_1")
        manager.send_message("conv_1", "Test")
        assert "conv_1" in manager.conversations

        manager.clear_conversation("conv_1")
        assert "conv_1" not in manager.conversations

    def test_list_conversations(self, manager):
        """Test listing conversations"""
        manager.start_conversation("conv_1")
        manager.start_conversation("conv_2")

        conversations = manager.list_conversations()
        assert len(conversations) == 2
        assert "conv_1" in conversations
        assert "conv_2" in conversations

    def test_history_trimming(self, manager):
        """Test that history is trimmed when it exceeds max_history"""
        manager.start_conversation("conv_1")

        # Send more messages than max_history
        for i in range(10):
            manager.send_message("conv_1", f"Message {i}")

        history = manager.get_history("conv_1")
        # max_history = 5, so 5 * 2 (user + assistant) = 10 messages
        assert len(history) <= manager.max_history * 2
