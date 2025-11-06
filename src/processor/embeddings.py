"""
Embeddings generation using sentence-transformers
"""
import logging
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for text chunks"""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None
    ):
        """
        Initialize embedding generator

        Args:
            model_name: Name of the sentence-transformers model
            device: Device to use ('cuda', 'cpu', or None for auto)
        """
        self.model_name = model_name
        logger.info(f"Loading embedding model: {model_name}")

        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dimension = self.model.get_sentence_embedding_dimension()

        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dimension}")

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text

        Args:
            text: Input text

        Returns:
            Embedding vector as numpy array
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return np.zeros(self.embedding_dimension)

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding

    def generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of input texts
            batch_size: Batch size for processing
            show_progress: Show progress bar

        Returns:
            Array of embeddings with shape (n_texts, embedding_dim)
        """
        if not texts:
            logger.warning("Empty text list provided")
            return np.array([])

        logger.info(f"Generating embeddings for {len(texts)} texts")

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )

        logger.info(f"Generated embeddings with shape: {embeddings.shape}")
        return embeddings

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model"""
        return self.embedding_dimension

    def encode_queries(
        self,
        queries: List[str],
        batch_size: int = 32
    ) -> np.ndarray:
        """
        Encode queries (alias for generate_embeddings for clarity)

        Args:
            queries: List of query strings
            batch_size: Batch size for processing

        Returns:
            Array of query embeddings
        """
        return self.generate_embeddings(queries, batch_size=batch_size)


class EmbeddingCache:
    """Simple in-memory cache for embeddings"""

    def __init__(self):
        self.cache = {}

    def get(self, text: str) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        return self.cache.get(text)

    def set(self, text: str, embedding: np.ndarray):
        """Store embedding in cache"""
        self.cache[text] = embedding

    def clear(self):
        """Clear the cache"""
        self.cache.clear()
        logger.info("Embedding cache cleared")

    def size(self) -> int:
        """Get number of cached embeddings"""
        return len(self.cache)


class CachedEmbeddingGenerator(EmbeddingGenerator):
    """Embedding generator with caching"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None):
        super().__init__(model_name, device)
        self.cache = EmbeddingCache()

    def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding with caching"""
        # Check cache first
        cached = self.cache.get(text)
        if cached is not None:
            return cached

        # Generate new embedding
        embedding = super().generate_embedding(text)

        # Store in cache
        self.cache.set(text, embedding)

        return embedding

    def generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True,
        use_cache: bool = True
    ) -> np.ndarray:
        """Generate embeddings with optional caching"""
        if not use_cache:
            return super().generate_embeddings(texts, batch_size, show_progress)

        # Check which texts need embedding
        embeddings = []
        texts_to_encode = []
        indices_to_encode = []

        for i, text in enumerate(texts):
            cached = self.cache.get(text)
            if cached is not None:
                embeddings.append((i, cached))
            else:
                texts_to_encode.append(text)
                indices_to_encode.append(i)

        # Generate embeddings for uncached texts
        if texts_to_encode:
            logger.info(f"Cache hit: {len(embeddings)}/{len(texts)}, generating {len(texts_to_encode)} new embeddings")
            new_embeddings = super().generate_embeddings(texts_to_encode, batch_size, show_progress)

            # Cache new embeddings
            for text, embedding in zip(texts_to_encode, new_embeddings):
                self.cache.set(text, embedding)
                embeddings.append((indices_to_encode[len(embeddings) - len(texts)], embedding))
        else:
            logger.info(f"All {len(texts)} embeddings found in cache")

        # Sort by original index and return
        embeddings.sort(key=lambda x: x[0])
        return np.array([emb for _, emb in embeddings])
