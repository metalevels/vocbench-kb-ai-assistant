"""
Tests for the processor module
"""
import pytest
from src.processor.text_cleaner import TextCleaner
from src.processor.text_chunker import TextChunker, TextChunk
from src.processor.embeddings import EmbeddingGenerator


class TestTextCleaner:
    """Test text cleaning functionality"""

    def test_clean_html(self):
        """Test HTML removal"""
        cleaner = TextCleaner()
        html_text = "<p>This is <b>bold</b> text.</p><script>alert('hi')</script>"
        cleaned = cleaner.clean_html(html_text)
        assert "bold" in cleaned
        assert "alert" not in cleaned
        assert "<p>" not in cleaned

    def test_remove_signatures(self):
        """Test signature removal"""
        cleaner = TextCleaner()
        text = "Message content here\n--\nBest regards,\nJohn Doe"
        cleaned = cleaner.remove_signatures(text)
        assert "Message content" in cleaned
        assert "Best regards" not in cleaned

    def test_normalize_whitespace(self):
        """Test whitespace normalization"""
        cleaner = TextCleaner()
        text = "Multiple    spaces\n\n\n\nmultiple newlines"
        cleaned = cleaner.normalize_whitespace(text)
        assert "Multiple spaces" in cleaned
        assert "   " not in cleaned

    def test_remove_quoted_text(self):
        """Test quoted text removal"""
        cleaner = TextCleaner()
        text = "My reply\n> Quoted text\n> More quotes\nMy continuation"
        cleaned = cleaner.remove_quoted_text(text)
        assert "My reply" in cleaned
        assert "Quoted text" not in cleaned

    def test_anonymize_emails(self):
        """Test email anonymization"""
        cleaner = TextCleaner()
        text = "Contact me at john@example.com for more info"
        cleaned = cleaner.anonymize_emails(text)
        assert "john@example.com" not in cleaned
        assert "[EMAIL]" in cleaned

    def test_full_clean(self):
        """Test complete cleaning pipeline"""
        cleaner = TextCleaner()
        text = """
        <p>Hello,</p>
        <p>Please contact me at test@example.com</p>
        > Previous message
        --
        Best regards
        """
        cleaned = cleaner.clean(text)
        assert "Hello" in cleaned
        assert "Please contact" in cleaned
        assert "[EMAIL]" in cleaned
        assert "Previous message" not in cleaned
        assert "Best regards" not in cleaned


class TestTextChunker:
    """Test text chunking functionality"""

    def test_chunk_short_text(self):
        """Test chunking text shorter than chunk size"""
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        text = "This is a short text that fits in one chunk."
        chunks = chunker.chunk_text(text, source_id="test_1")

        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].source_id == "test_1"

    def test_chunk_long_text(self):
        """Test chunking text longer than chunk size"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        # Create a text longer than 100 characters
        text = "Paragraph one with some content. " * 5 + "\n\n" + "Paragraph two with more content. " * 5
        chunks = chunker.chunk_text(text, source_id="test_2")

        assert len(chunks) > 1
        assert all(isinstance(chunk, TextChunk) for chunk in chunks)

    def test_chunk_with_metadata(self):
        """Test chunking with metadata preservation"""
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        text = "Test content"
        metadata = {"author": "John", "date": "2024-01-15"}
        chunks = chunker.chunk_text(text, source_id="test_3", metadata=metadata)

        assert chunks[0].metadata["author"] == "John"
        assert chunks[0].metadata["date"] == "2024-01-15"

    def test_chunk_messages(self):
        """Test chunking multiple messages"""
        chunker = TextChunker(chunk_size=200, chunk_overlap=50)
        messages = [
            {
                "message_id": "msg_1",
                "thread_id": "thread_1",
                "subject": "Test Subject",
                "body": "This is the message body.",
                "author": "John",
                "date": "2024-01-15"
            },
            {
                "message_id": "msg_2",
                "thread_id": "thread_1",
                "subject": "Re: Test Subject",
                "body": "This is a reply.",
                "author": "Jane",
                "date": "2024-01-16"
            }
        ]

        chunks = chunker.chunk_messages(messages, combine_thread=False)
        assert len(chunks) >= 2  # At least one chunk per message
        assert any("Test Subject" in chunk.content for chunk in chunks)


class TestEmbeddingGenerator:
    """Test embedding generation"""

    @pytest.fixture
    def generator(self):
        """Create embedding generator"""
        # Use a small model for testing
        return EmbeddingGenerator(model_name="all-MiniLM-L6-v2")

    def test_generate_single_embedding(self, generator):
        """Test generating a single embedding"""
        text = "This is a test sentence for embedding."
        embedding = generator.generate_embedding(text)

        assert embedding is not None
        assert len(embedding) == generator.embedding_dimension
        assert embedding.shape[0] > 0

    def test_generate_multiple_embeddings(self, generator):
        """Test generating multiple embeddings"""
        texts = [
            "First test sentence.",
            "Second test sentence.",
            "Third test sentence."
        ]
        embeddings = generator.generate_embeddings(texts, show_progress=False)

        assert embeddings.shape[0] == 3
        assert embeddings.shape[1] == generator.embedding_dimension

    def test_empty_text_handling(self, generator):
        """Test handling of empty text"""
        embedding = generator.generate_embedding("")
        assert embedding is not None
        assert len(embedding) == generator.embedding_dimension

    def test_embedding_dimension(self, generator):
        """Test getting embedding dimension"""
        dim = generator.get_embedding_dimension()
        assert dim > 0
        assert isinstance(dim, int)


@pytest.fixture
def sample_messages():
    """Fixture providing sample messages"""
    return [
        {
            "message_id": "msg_1",
            "thread_id": "thread_1",
            "subject": "SPARQL Configuration",
            "body": "<p>How do I configure SPARQL endpoint?</p>",
            "author": "John",
            "date": "2024-01-15T10:30:00Z"
        },
        {
            "message_id": "msg_2",
            "thread_id": "thread_1",
            "subject": "Re: SPARQL Configuration",
            "body": "You can configure it in settings.\n> How do I configure SPARQL endpoint?\n--\nBest regards",
            "author": "Jane",
            "date": "2024-01-15T14:20:00Z"
        }
    ]
