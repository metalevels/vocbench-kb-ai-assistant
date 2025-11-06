"""
Text chunking utilities for optimal embedding generation
"""
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata"""
    content: str
    chunk_index: int
    source_id: str  # thread_id or message_id
    metadata: dict


class TextChunker:
    """Splits text into chunks for embedding generation"""

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        separator: str = "\n\n"
    ):
        """
        Initialize chunker

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            separator: Primary separator for splitting (paragraphs by default)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def _split_by_separator(self, text: str, separator: str) -> List[str]:
        """Split text by separator"""
        return [s.strip() for s in text.split(separator) if s.strip()]

    def chunk_text(self, text: str, source_id: str, metadata: Optional[dict] = None) -> List[TextChunk]:
        """
        Chunk a single text into multiple chunks

        Args:
            text: Text to chunk
            source_id: Identifier of the source (thread_id, message_id)
            metadata: Additional metadata to attach to chunks

        Returns:
            List of TextChunk objects
        """
        if not text:
            return []

        if metadata is None:
            metadata = {}

        chunks = []

        # First, try splitting by paragraphs
        paragraphs = self._split_by_separator(text, self.separator)

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            # If adding this paragraph exceeds chunk size
            if len(current_chunk) + len(para) + len(self.separator) > self.chunk_size:
                # Save current chunk if it's not empty
                if current_chunk:
                    chunks.append(TextChunk(
                        content=current_chunk.strip(),
                        chunk_index=chunk_index,
                        source_id=source_id,
                        metadata=metadata.copy()
                    ))
                    chunk_index += 1

                    # Start new chunk with overlap if the paragraph is short enough
                    if len(para) <= self.chunk_size:
                        # Include overlap from previous chunk
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                        current_chunk = overlap_text + self.separator + para
                    else:
                        # Paragraph is too long, need to split it further
                        # Split by sentences or words
                        sub_chunks = self._split_long_text(para, self.chunk_size, self.chunk_overlap)
                        for sub_chunk in sub_chunks:
                            chunks.append(TextChunk(
                                content=sub_chunk.strip(),
                                chunk_index=chunk_index,
                                source_id=source_id,
                                metadata=metadata.copy()
                            ))
                            chunk_index += 1
                        current_chunk = ""
                else:
                    # First paragraph is too long
                    if len(para) > self.chunk_size:
                        sub_chunks = self._split_long_text(para, self.chunk_size, self.chunk_overlap)
                        for sub_chunk in sub_chunks:
                            chunks.append(TextChunk(
                                content=sub_chunk.strip(),
                                chunk_index=chunk_index,
                                source_id=source_id,
                                metadata=metadata.copy()
                            ))
                            chunk_index += 1
                    else:
                        current_chunk = para
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += self.separator + para
                else:
                    current_chunk = para

        # Add the last chunk
        if current_chunk:
            chunks.append(TextChunk(
                content=current_chunk.strip(),
                chunk_index=chunk_index,
                source_id=source_id,
                metadata=metadata.copy()
            ))

        logger.debug(f"Split text of length {len(text)} into {len(chunks)} chunks")
        return chunks

    def _split_long_text(self, text: str, max_size: int, overlap: int) -> List[str]:
        """
        Split text that's longer than max_size into smaller chunks

        Args:
            text: Text to split
            max_size: Maximum size of each chunk
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + max_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending punctuation
                last_period = max(chunk.rfind('.'), chunk.rfind('!'), chunk.rfind('?'))
                if last_period > max_size // 2:  # Only break if we're past halfway
                    chunk = chunk[:last_period + 1]
                    end = start + last_period + 1

            chunks.append(chunk)
            start = end - overlap if end < len(text) else end

        return chunks

    def chunk_messages(
        self,
        messages: List[dict],
        combine_thread: bool = False
    ) -> List[TextChunk]:
        """
        Chunk multiple messages

        Args:
            messages: List of message dicts with 'body', 'message_id', 'subject', etc.
            combine_thread: If True, combine all messages in same thread

        Returns:
            List of TextChunk objects
        """
        all_chunks = []

        if combine_thread:
            # Group messages by thread_id
            threads = {}
            for msg in messages:
                thread_id = msg.get('thread_id', 'unknown')
                if thread_id not in threads:
                    threads[thread_id] = []
                threads[thread_id].append(msg)

            # Chunk each thread
            for thread_id, thread_messages in threads.items():
                # Combine all messages in thread
                combined_text = "\n\n".join([
                    f"Subject: {msg.get('subject', '')}\n{msg.get('body', '')}"
                    for msg in sorted(thread_messages, key=lambda m: m.get('date', ''))
                ])

                metadata = {
                    'thread_id': thread_id,
                    'message_count': len(thread_messages),
                    'first_date': thread_messages[0].get('date') if thread_messages else None
                }

                chunks = self.chunk_text(combined_text, thread_id, metadata)
                all_chunks.extend(chunks)
        else:
            # Chunk each message individually
            for msg in messages:
                text = f"Subject: {msg.get('subject', '')}\n\n{msg.get('body', '')}"
                metadata = {
                    'thread_id': msg.get('thread_id'),
                    'message_id': msg.get('message_id'),
                    'author': msg.get('author'),
                    'date': msg.get('date'),
                    'subject': msg.get('subject')
                }

                chunks = self.chunk_text(text, msg.get('message_id', 'unknown'), metadata)
                all_chunks.extend(chunks)

        logger.info(f"Created {len(all_chunks)} chunks from {len(messages)} messages")
        return all_chunks
