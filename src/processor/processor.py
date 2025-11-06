"""
Main processor orchestrating text cleaning, chunking, and embedding generation
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.processor.text_cleaner import TextCleaner
from src.processor.text_chunker import TextChunker, TextChunk
from src.processor.embeddings import CachedEmbeddingGenerator
from config.settings import settings

logger = logging.getLogger(__name__)


class DataProcessor:
    """Orchestrates the entire data processing pipeline"""

    def __init__(
        self,
        embedding_model: str = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
        output_dir: str = "./data/processed"
    ):
        """
        Initialize processor

        Args:
            embedding_model: Name of embedding model (from settings if None)
            chunk_size: Size of text chunks (from settings if None)
            chunk_overlap: Overlap between chunks (from settings if None)
            output_dir: Directory for processed output
        """
        self.text_cleaner = TextCleaner()
        self.text_chunker = TextChunker(
            chunk_size=chunk_size or settings.chunk_size,
            chunk_overlap=chunk_overlap or settings.chunk_overlap
        )
        self.embedding_generator = CachedEmbeddingGenerator(
            model_name=embedding_model or settings.embedding_model
        )

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("DataProcessor initialized")

    def process_scraped_data(
        self,
        input_file: str,
        combine_threads: bool = False,
        clean_config: Optional[Dict[str, bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process scraped data from JSON file

        Args:
            input_file: Path to scraped data JSON file
            combine_threads: Whether to combine messages by thread
            clean_config: Configuration for text cleaning

        Returns:
            List of processed chunks with embeddings
        """
        logger.info(f"Processing scraped data from {input_file}")

        # Load scraped data
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        threads = data.get('threads', [])
        logger.info(f"Loaded {len(threads)} threads")

        # Extract all messages
        all_messages = []
        for thread in threads:
            for message in thread.get('messages', []):
                all_messages.append(message)

        logger.info(f"Extracted {len(all_messages)} messages")

        # Process messages
        return self.process_messages(all_messages, combine_threads, clean_config)

    def process_messages(
        self,
        messages: List[Dict[str, Any]],
        combine_threads: bool = False,
        clean_config: Optional[Dict[str, bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process messages through the pipeline

        Args:
            messages: List of message dicts
            combine_threads: Whether to combine messages by thread
            clean_config: Configuration for text cleaning

        Returns:
            List of processed chunks with embeddings
        """
        if clean_config is None:
            clean_config = {
                'remove_html': True,
                'remove_sigs': True,
                'remove_quotes': True,
                'anonymize_email': True,
                'shorten_url': False
            }

        # Step 1: Clean message bodies
        logger.info("Step 1: Cleaning text")
        for message in messages:
            if 'body' in message:
                message['body'] = self.text_cleaner.clean(
                    message['body'],
                    **clean_config
                )

        # Step 2: Chunk messages
        logger.info("Step 2: Chunking text")
        chunks = self.text_chunker.chunk_messages(messages, combine_threads)
        logger.info(f"Created {len(chunks)} chunks")

        # Step 3: Generate embeddings
        logger.info("Step 3: Generating embeddings")
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedding_generator.generate_embeddings(
            texts,
            batch_size=32,
            show_progress=True
        )

        # Step 4: Combine chunks with embeddings
        logger.info("Step 4: Combining chunks with embeddings")
        processed_data = []
        for chunk, embedding in zip(chunks, embeddings):
            processed_data.append({
                'chunk_id': f"{chunk.source_id}_chunk_{chunk.chunk_index}",
                'source_id': chunk.source_id,
                'chunk_index': chunk.chunk_index,
                'content': chunk.content,
                'embedding': embedding.tolist(),
                'metadata': chunk.metadata
            })

        logger.info(f"Processing complete. Generated {len(processed_data)} embedded chunks")
        return processed_data

    def save_processed_data(
        self,
        processed_data: List[Dict[str, Any]],
        filename: str = "processed_data.json"
    ):
        """
        Save processed data to JSON

        Args:
            processed_data: List of processed chunks
            filename: Output filename
        """
        output_path = self.output_dir / filename

        output = {
            'processed_at': datetime.now().isoformat(),
            'total_chunks': len(processed_data),
            'embedding_model': self.embedding_generator.model_name,
            'embedding_dimension': self.embedding_generator.embedding_dimension,
            'chunks': processed_data
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(processed_data)} processed chunks to {output_path}")

        # Also save metadata separately (without embeddings) for easier inspection
        metadata_path = self.output_dir / filename.replace('.json', '_metadata.json')
        metadata = {
            'processed_at': output['processed_at'],
            'total_chunks': output['total_chunks'],
            'embedding_model': output['embedding_model'],
            'embedding_dimension': output['embedding_dimension'],
            'chunks': [
                {k: v for k, v in chunk.items() if k != 'embedding'}
                for chunk in processed_data
            ]
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved metadata to {metadata_path}")

    def load_processed_data(self, filename: str = "processed_data.json") -> List[Dict[str, Any]]:
        """
        Load processed data from JSON

        Args:
            filename: Input filename

        Returns:
            List of processed chunks
        """
        input_path = self.output_dir / filename

        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        chunks = data.get('chunks', [])
        logger.info(f"Loaded {len(chunks)} processed chunks from {input_path}")

        return chunks

    def get_statistics(self, processed_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get statistics about processed data

        Args:
            processed_data: List of processed chunks

        Returns:
            Dictionary of statistics
        """
        if not processed_data:
            return {}

        chunk_sizes = [len(chunk['content']) for chunk in processed_data]
        source_ids = set(chunk['source_id'] for chunk in processed_data)

        stats = {
            'total_chunks': len(processed_data),
            'unique_sources': len(source_ids),
            'avg_chunk_size': sum(chunk_sizes) / len(chunk_sizes),
            'min_chunk_size': min(chunk_sizes),
            'max_chunk_size': max(chunk_sizes),
            'embedding_dimension': len(processed_data[0]['embedding']) if processed_data else 0
        }

        return stats
