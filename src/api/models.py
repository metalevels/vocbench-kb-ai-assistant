"""
API request and response models
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., description="User's message", min_length=1)
    conversation_id: Optional[str] = Field(None, description="Conversation ID for maintaining context")
    top_k: int = Field(5, description="Number of relevant documents to retrieve", ge=1, le=20)
    include_sources: bool = Field(True, description="Include source documents in response")


class Source(BaseModel):
    """Source document model"""
    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    score: float = Field(..., description="Relevance score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str = Field(..., description="Assistant's response")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    sources: List[Source] = Field(default_factory=list, description="Source documents used")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")


class SearchRequest(BaseModel):
    """Request model for search endpoint"""
    query: str = Field(..., description="Search query", min_length=1)
    top_k: int = Field(10, description="Number of results to return", ge=1, le=50)
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    min_score: Optional[float] = Field(None, description="Minimum similarity score", ge=0, le=1)


class SearchResult(BaseModel):
    """Search result model"""
    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    score: float = Field(..., description="Relevance score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class SearchResponse(BaseModel):
    """Response model for search endpoint"""
    query: str = Field(..., description="Original query")
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Number of results returned")


class IndexRequest(BaseModel):
    """Request model for indexing endpoint"""
    source_file: str = Field(..., description="Path to processed data JSON file")
    clear_existing: bool = Field(False, description="Clear existing index before indexing")


class IndexResponse(BaseModel):
    """Response model for indexing endpoint"""
    status: str = Field(..., description="Status of indexing operation")
    documents_indexed: int = Field(..., description="Number of documents indexed")
    total_documents: int = Field(..., description="Total documents in collection")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    vector_store_status: str = Field(..., description="Vector store status")
    total_documents: int = Field(..., description="Total documents indexed")


class StatsResponse(BaseModel):
    """Response model for statistics"""
    total_documents: int = Field(..., description="Total documents in vector store")
    collection_name: str = Field(..., description="Collection name")
    embedding_model: str = Field(..., description="Embedding model used")
    embedding_dimension: int = Field(..., description="Embedding dimension")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
