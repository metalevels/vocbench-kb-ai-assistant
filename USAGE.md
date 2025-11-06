# VocBench Knowledge Chat - Usage Guide

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd vocbench-ai-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### 2. Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_api_key_here
```

### 3. Run End-to-End Test

Test the entire pipeline with synthetic data:

```bash
python scripts/e2e_test.py
```

This will:
- Process synthetic VocBench discussion data
- Generate embeddings
- Index into ChromaDB
- Test semantic retrieval
- Verify the chat interface setup

## Usage Workflows

### Workflow 1: Scrape and Index Google Group Data

```bash
# Step 1: Scrape Google Group
python -m src.scraper.main --max-threads 50 --output scraped_data.json

# Step 2: Process scraped data
python -c "
from src.processor.processor import DataProcessor
processor = DataProcessor()
data = processor.process_scraped_data('data/raw/scraped_data.json')
processor.save_processed_data(data, 'processed_data.json')
"

# Step 3: Index into vector database
python -c "
from src.processor.processor import DataProcessor
from src.retrieval.vector_store import VectorStore, VectorStoreManager

processor = DataProcessor()
data = processor.load_processed_data('processed_data.json')

vector_store = VectorStore()
manager = VectorStoreManager(vector_store)
manager.index_processed_data(data)
print(f'Indexed {vector_store.count()} documents')
"
```

### Workflow 2: Use Pre-Indexed Data with API

```bash
# Start the API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload
```

Access the API:
- Interactive docs: http://localhost:8080/docs
- Health check: http://localhost:8080/health
- Statistics: http://localhost:8080/stats

### Workflow 3: Chat via API

```bash
# Chat request
curl -X POST "http://localhost:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How do I configure a SPARQL endpoint in VocBench?",
    "top_k": 5,
    "include_sources": true
  }'

# Search request
curl -X POST "http://localhost:8080/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SPARQL configuration",
    "top_k": 10
  }'
```

### Workflow 4: Programmatic Usage

```python
from src.retrieval.vector_store import VectorStore
from src.retrieval.retriever import SemanticRetriever
from src.processor.embeddings import EmbeddingGenerator
from src.conversation.chat import VocBenchAssistant

# Initialize components
vector_store = VectorStore()
embedding_generator = EmbeddingGenerator()
retriever = SemanticRetriever(vector_store, embedding_generator)
assistant = VocBenchAssistant(retriever)

# Chat
result = assistant.chat("How do I import a SKOS vocabulary?")
print(result['response'])
print(f"\nSources used: {len(result['sources'])}")
```

## Docker Deployment

### Using Docker Compose

```bash
# Build and start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services:
- `chromadb`: Vector database at http://localhost:8000
- `vocbench-api`: API server at http://localhost:8080

### Run Scraper with Docker

```bash
# Run scraper
docker-compose --profile scraper run scraper --max-threads 50
```

## Advanced Usage

### Custom Embeddings Model

```python
from src.processor.embeddings import EmbeddingGenerator

# Use a different model
generator = EmbeddingGenerator(model_name="all-mpnet-base-v2")
```

### Hybrid Search

```python
from src.retrieval.retriever import SemanticRetriever

# Combine semantic and keyword search
results = retriever.hybrid_search(
    query="SPARQL endpoint",
    semantic_weight=0.7,
    keyword_weight=0.3
)
```

### Context-Aware Retrieval

```python
# Get surrounding chunks for better context
results = retriever.retrieve_with_context(
    query="How to configure SPARQL?",
    context_window=1  # Include 1 chunk before and after
)
```

### Conversation with History

```python
from src.conversation.chat import ConversationManager

conv_manager = ConversationManager(assistant)

# Multi-turn conversation
conv_manager.send_message("conv_1", "What is VocBench?")
conv_manager.send_message("conv_1", "How do I install it?")
conv_manager.send_message("conv_1", "What are the system requirements?")

# View history
history = conv_manager.get_history("conv_1")
```

## Testing

Run all tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test module
pytest tests/test_processor.py -v

# Run end-to-end test
python scripts/e2e_test.py
```

## Monitoring and Maintenance

### Check System Health

```bash
curl http://localhost:8080/health
```

### View Statistics

```bash
curl http://localhost:8080/stats
```

### Reindex Data

```bash
curl -X POST "http://localhost:8080/index" \
  -H "Content-Type: application/json" \
  -d '{
    "source_file": "processed_data.json",
    "clear_existing": true
  }'
```

## Troubleshooting

### ChromaDB Connection Issues

If ChromaDB fails to connect:

```bash
# Check if ChromaDB is running
docker ps | grep chroma

# Restart ChromaDB
docker-compose restart chromadb
```

### Low Retrieval Quality

If search results are not relevant:

1. Try increasing `top_k` parameter
2. Use hybrid search for better keyword matching
3. Adjust chunking parameters in settings
4. Reprocess data with different chunk sizes

### API Errors

Check logs:

```bash
# Docker logs
docker-compose logs vocbench-api

# Local logs
tail -f logs/api.log
```

## Performance Optimization

### Batch Processing

Process large datasets in batches:

```python
manager.index_processed_data(data, batch_size=100)
```

### Caching

Use cached embedding generator:

```python
from src.processor.embeddings import CachedEmbeddingGenerator

generator = CachedEmbeddingGenerator()
# Subsequent calls with same text will use cache
```

### Resource Limits

Adjust in `.env`:

```
API_WORKERS=4
CHUNK_SIZE=600
CHUNK_OVERLAP=100
```

## Next Steps

1. **Production Deployment**: Configure proper CORS, authentication, and rate limiting
2. **Scheduled Scraping**: Set up cron jobs for regular data updates
3. **Monitoring**: Integrate with monitoring tools (Prometheus, Grafana)
4. **Scaling**: Use distributed ChromaDB or other vector databases for large scale
