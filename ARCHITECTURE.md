# System Architecture

## Overview

VocBench Knowledge Chat is a RAG (Retrieval-Augmented Generation) system that provides conversational access to knowledge from the VocBench Google Group discussions.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       Data Ingestion Layer                       │
├─────────────────────────────────────────────────────────────────┤
│  Google Group → Scraper → Raw JSON → Processor → Embeddings     │
│                    │                      │                      │
│                    │                      ├─ Text Cleaning       │
│                    │                      ├─ Chunking            │
│                    │                      └─ Embedding Gen       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                       Storage Layer                              │
├─────────────────────────────────────────────────────────────────┤
│                      ChromaDB Vector Store                       │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Vectors    │  │   Documents  │  │   Metadata   │         │
│  │  (384-dim)   │  │   (Text)     │  │  (JSON)      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Retrieval Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  Query → Embedding → Vector Search → Ranking → Top-K Results    │
│                                                                  │
│  Features: Semantic Search, Hybrid Search, Context Window       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Generation Layer                              │
├─────────────────────────────────────────────────────────────────┤
│                    Anthropic Claude API                          │
│                                                                  │
│  Context + Query → LLM → Response                               │
│                                                                  │
│  Model: Claude 3.5 Sonnet                                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
├─────────────────────────────────────────────────────────────────┤
│                       FastAPI Server                             │
│                                                                  │
│  Endpoints: /chat, /search, /index, /health, /stats            │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Scraper Module (`src/scraper/`)

**Purpose**: Extract discussions from Google Groups

**Components**:
- `google_groups_scraper.py`: Web scraper with rate limiting and retry logic
- `models.py`: Data models (Message, Thread, ScraperStats)
- `main.py`: CLI interface for scraping

**Features**:
- Pagination support
- Rate limiting
- Error handling and retry logic
- JSON export
- Incremental updates (planned)

### 2. Processor Module (`src/processor/`)

**Purpose**: Transform raw text into embeddings

**Components**:
- `text_cleaner.py`: HTML removal, signature detection, email anonymization
- `text_chunker.py`: Smart chunking with overlap
- `embeddings.py`: Embedding generation with caching
- `processor.py`: Orchestrator for the pipeline

**Processing Pipeline**:
1. **Text Cleaning**:
   - Remove HTML tags
   - Remove email signatures
   - Remove quoted text
   - Anonymize emails
   - Normalize whitespace

2. **Chunking**:
   - Target size: 600 characters
   - Overlap: 100 characters
   - Preserve paragraph boundaries
   - Include metadata

3. **Embedding**:
   - Model: `all-MiniLM-L6-v2` (384-dim)
   - Batch processing
   - Caching for efficiency

### 3. Retrieval Module (`src/retrieval/`)

**Purpose**: Semantic search over vector store

**Components**:
- `vector_store.py`: ChromaDB interface
- `retriever.py`: Semantic retrieval with ranking

**Search Strategies**:
- **Semantic Search**: Pure vector similarity
- **Hybrid Search**: Combines semantic + keyword matching
- **Context-Aware**: Retrieves surrounding chunks

**Ranking**:
- L2 distance → similarity score
- Configurable threshold filtering
- Top-K selection

### 4. Conversation Module (`src/conversation/`)

**Purpose**: RAG-powered conversational interface

**Components**:
- `chat.py`: VocBenchAssistant and ConversationManager

**RAG Pattern**:
1. Retrieve relevant documents (top-k)
2. Format as context for LLM
3. Inject into prompt
4. Generate response with Claude
5. Return response + sources

**Features**:
- Conversation history management
- Streaming responses
- Custom system prompts
- Token usage tracking

### 5. API Module (`src/api/`)

**Purpose**: REST API for external access

**Components**:
- `main.py`: FastAPI application
- `models.py`: Request/response models

**Endpoints**:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat` | POST | Chat with assistant |
| `/chat/stream` | POST | Stream chat response |
| `/search` | POST | Semantic search |
| `/index` | POST | Index new data |
| `/health` | GET | Health check |
| `/stats` | GET | System statistics |
| `/conversations/{id}` | DELETE | Clear conversation |

## Data Flow

### Indexing Flow

```
Raw Scrape → Clean → Chunk → Embed → Index
    ↓          ↓       ↓       ↓       ↓
  JSON      Text    Chunks  Vectors  ChromaDB
```

### Query Flow

```
User Query → Embed → Search → Rank → Context
    ↓         ↓        ↓       ↓        ↓
  Text    Vector   ChromaDB  Top-K   Format
                                        ↓
                                    Claude API
                                        ↓
                                    Response
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| LLM | Anthropic Claude 3.5 Sonnet | Response generation |
| Vector DB | ChromaDB | Similarity search |
| Embeddings | sentence-transformers | Text→Vector |
| API | FastAPI | REST interface |
| Processing | Python 3.11+ | Data pipeline |
| Testing | pytest | Unit/integration tests |
| Deployment | Docker + docker-compose | Containerization |

## Design Decisions

### Why ChromaDB?

- **Embedded mode**: No server required for development
- **Client-server mode**: Easy scaling
- **Metadata filtering**: Rich query capabilities
- **Python-native**: Seamless integration

### Why sentence-transformers?

- **Fast inference**: CPU-friendly
- **Good quality**: Strong semantic understanding
- **Flexible**: Easy to swap models
- **Lightweight**: `all-MiniLM-L6-v2` is only 80MB

### Why Claude?

- **Context window**: 200K tokens
- **Quality**: Excellent instruction following
- **Streaming**: Real-time responses
- **Safety**: Built-in content filtering

### Chunking Strategy

- **Paragraph-aware**: Preserves semantic boundaries
- **Overlap**: Ensures context continuity
- **Metadata preservation**: Tracks source information
- **Configurable**: Adaptable to different content types

## Scalability Considerations

### Current Limitations

- Single ChromaDB instance
- No distributed processing
- In-memory conversation management
- No authentication/authorization

### Scaling Strategies

1. **Horizontal Scaling**:
   - Separate scraper, processor, and API services
   - Multiple API workers
   - Load balancing

2. **Vector Store Scaling**:
   - Use ChromaDB server mode
   - Consider Weaviate or Milvus for >10M vectors
   - Implement sharding for geographic distribution

3. **Processing Scaling**:
   - Batch processing with queues (Celery, RQ)
   - Parallel embedding generation
   - Distributed embedding models (Ray, Dask)

4. **Caching**:
   - Redis for conversation state
   - CDN for static assets
   - Query result caching

## Security Considerations

1. **Data Privacy**:
   - Email anonymization in processing
   - No PII in vector store
   - Public data only

2. **API Security**:
   - Rate limiting (TODO)
   - API key authentication (TODO)
   - CORS configuration
   - Input validation

3. **Secrets Management**:
   - Environment variables
   - `.env` files excluded from git
   - Secure key storage for production

## Monitoring and Observability

### Current Metrics

- Document count
- Token usage
- Search latency
- API response times

### Recommended Additions

1. **Application Metrics**:
   - Prometheus + Grafana
   - Custom metrics for retrieval quality
   - Error rates and types

2. **Logging**:
   - Structured logging (JSON)
   - Centralized log aggregation (ELK stack)
   - Alert on critical errors

3. **Tracing**:
   - OpenTelemetry for distributed tracing
   - End-to-end request tracking

## Future Enhancements

1. **Multi-modal Support**: Images, PDFs from discussions
2. **Fine-tuned Embeddings**: Domain-specific models
3. **Active Learning**: User feedback loop
4. **Multi-language**: Support for non-English content
5. **Real-time Updates**: Webhook-based scraping
6. **Advanced Retrieval**: Re-ranking, query expansion
