"""
Data models for scraped Google Group content
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represents a single message/post in a thread"""
    message_id: str = Field(..., description="Unique message identifier")
    thread_id: str = Field(..., description="Parent thread identifier")
    author: str = Field(..., description="Message author name")
    author_email: Optional[str] = Field(None, description="Author email if available")
    date: datetime = Field(..., description="Message timestamp")
    subject: str = Field(..., description="Message subject/title")
    body: str = Field(..., description="Message body content")
    is_first_message: bool = Field(default=False, description="Whether this starts a thread")
    reply_to: Optional[str] = Field(None, description="ID of message being replied to")
    url: str = Field(..., description="Original URL of the message")

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_12345",
                "thread_id": "thread_67890",
                "author": "John Doe",
                "author_email": "john@example.com",
                "date": "2024-01-15T10:30:00Z",
                "subject": "Question about VocBench SPARQL queries",
                "body": "How can I perform custom SPARQL queries in VocBench?",
                "is_first_message": True,
                "reply_to": None,
                "url": "https://groups.google.com/g/vocbench-user/c/abc123"
            }
        }


class Thread(BaseModel):
    """Represents a discussion thread"""
    thread_id: str = Field(..., description="Unique thread identifier")
    subject: str = Field(..., description="Thread subject")
    first_message_date: datetime = Field(..., description="When thread was started")
    last_message_date: datetime = Field(..., description="Last activity in thread")
    message_count: int = Field(default=0, description="Number of messages in thread")
    messages: List[Message] = Field(default_factory=list, description="All messages in thread")
    url: str = Field(..., description="Original thread URL")

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "thread_67890",
                "subject": "Question about VocBench SPARQL queries",
                "first_message_date": "2024-01-15T10:30:00Z",
                "last_message_date": "2024-01-16T14:20:00Z",
                "message_count": 3,
                "messages": [],
                "url": "https://groups.google.com/g/vocbench-user/c/abc123"
            }
        }


class ScraperStats(BaseModel):
    """Statistics about scraping operation"""
    total_threads: int = 0
    total_messages: int = 0
    successful_threads: int = 0
    failed_threads: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration of scraping operation"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
