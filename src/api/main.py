"""
FastAPI application for VocBench Knowledge Chat
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.api.models import (
    ChatRequest, ChatResponse, SearchRequest, SearchResponse,
    IndexRequest, IndexResponse, HealthResponse, StatsResponse,
    Source, SearchResult, ErrorResponse
)
from src.api import scraper_routes
from src.retrieval.vector_store import VectorStore, VectorStoreManager
from src.retrieval.retriever import SemanticRetriever
from src.processor.embeddings import EmbeddingGenerator
from src.processor.processor import DataProcessor
from src.conversation.chat import VocBenchAssistant, ConversationManager
from config.settings import settings

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances (initialized in lifespan)
vector_store: Optional[VectorStore] = None
retriever: Optional[SemanticRetriever] = None
assistant: Optional[VocBenchAssistant] = None
conversation_manager: Optional[ConversationManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global vector_store, retriever, assistant, conversation_manager

    logger.info("Initializing VocBench Knowledge Chat API")

    # Initialize components
    try:
        # Vector store
        vector_store = VectorStore(
            collection_name="vocbench_knowledge",
            persist_directory=settings.chroma_persist_dir,
            host=settings.vector_db_host if settings.vector_db_type == "chromadb_server" else None,
            port=settings.vector_db_port if settings.vector_db_type == "chromadb_server" else None
        )
        logger.info("Vector store initialized")

        # Embedding generator
        embedding_generator = EmbeddingGenerator(
            model_name=settings.embedding_model
        )
        logger.info("Embedding generator initialized")

        # Retriever
        retriever = SemanticRetriever(
            vector_store=vector_store,
            embedding_generator=embedding_generator,
            default_top_k=5
        )
        logger.info("Retriever initialized")

        # Assistant
        assistant = VocBenchAssistant(
            retriever=retriever,
            api_key=settings.anthropic_api_key
        )
        logger.info("Assistant initialized")

        # Conversation manager
        conversation_manager = ConversationManager(assistant, max_history=10)
        logger.info("Conversation manager initialized")

        logger.info("API initialization complete")

    except Exception as e:
        logger.error(f"Failed to initialize API: {e}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down API")


# Create FastAPI app
app = FastAPI(
    title="VocBench Knowledge Chat API",
    description="Conversational AI assistant for VocBench Google Group knowledge",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include scraper routes
app.include_router(scraper_routes.router)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/console", response_class=HTMLResponse, tags=["Console"])
async def scraper_console():
    """
    Scraper web console

    Access the interactive scraper management console.
    """
    console_file = static_dir / "scraper_console.html"
    if console_file.exists():
        with open(console_file, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        raise HTTPException(status_code=404, detail="Console not found")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "VocBench Knowledge Chat API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    try:
        doc_count = vector_store.count() if vector_store else 0
        vector_status = "ok" if vector_store else "not_initialized"

        return HealthResponse(
            status="healthy",
            version="0.1.0",
            vector_store_status=vector_status,
            total_documents=doc_count
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Chat with the VocBench assistant

    The assistant retrieves relevant knowledge from the VocBench Google Group
    and provides contextual answers using Claude.
    """
    try:
        if not assistant or not conversation_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Assistant not initialized"
            )

        # Use conversation manager if conversation_id provided
        if request.conversation_id:
            result = conversation_manager.send_message(
                conversation_id=request.conversation_id,
                user_message=request.message,
                top_k=request.top_k
            )
        else:
            result = assistant.chat(
                user_message=request.message,
                top_k=request.top_k,
                include_sources=request.include_sources
            )

        # Format sources
        sources = [
            Source(
                id=src['id'],
                content=src['content'],
                score=src['score'],
                metadata=src.get('metadata', {})
            )
            for src in result.get('sources', [])
        ] if request.include_sources else []

        return ChatResponse(
            response=result['response'],
            conversation_id=request.conversation_id,
            sources=sources,
            usage=result.get('usage')
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """
    Stream chat response from the assistant

    Returns a streaming response with the assistant's answer.
    """
    try:
        if not assistant:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Assistant not initialized"
            )

        # Get conversation history if conversation_id provided
        history = None
        if request.conversation_id and conversation_manager:
            history = conversation_manager.get_history(request.conversation_id)

        # Stream response
        async def generate():
            for chunk in assistant.stream_chat(
                user_message=request.message,
                conversation_history=history,
                top_k=request.top_k
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Stream chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search(request: SearchRequest):
    """
    Search for relevant documents in the knowledge base

    Performs semantic search without generating a conversational response.
    """
    try:
        if not retriever:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Retriever not initialized"
            )

        results = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            min_score=request.min_score
        )

        search_results = [
            SearchResult(
                id=r['id'],
                content=r['content'],
                score=r['score'],
                metadata=r.get('metadata', {})
            )
            for r in results
        ]

        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results)
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/index", response_model=IndexResponse, tags=["Admin"])
async def index_data(request: IndexRequest):
    """
    Index processed data into the vector store

    Requires a path to a processed data JSON file.
    """
    try:
        if not vector_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vector store not initialized"
            )

        # Load processed data
        processor = DataProcessor()
        processed_data = processor.load_processed_data(request.source_file)

        # Index data
        manager = VectorStoreManager(vector_store)

        if request.clear_existing:
            documents_indexed = manager.reindex(processed_data)
        else:
            documents_indexed = manager.index_processed_data(processed_data)

        total_docs = vector_store.count()

        return IndexResponse(
            status="success",
            documents_indexed=documents_indexed,
            total_documents=total_docs
        )

    except Exception as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/stats", response_model=StatsResponse, tags=["Info"])
async def get_stats():
    """Get statistics about the knowledge base"""
    try:
        if not vector_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vector store not initialized"
            )

        stats = vector_store.get_statistics()

        return StatsResponse(
            total_documents=stats['total_documents'],
            collection_name=stats['collection_name'],
            embedding_model=settings.embedding_model,
            embedding_dimension=settings.embedding_dimension
        )

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete("/conversations/{conversation_id}", tags=["Chat"])
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its history"""
    try:
        if not conversation_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Conversation manager not initialized"
            )

        conversation_manager.clear_conversation(conversation_id)

        return {"status": "success", "message": f"Conversation {conversation_id} deleted"}

    except Exception as e:
        logger.error(f"Delete conversation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
