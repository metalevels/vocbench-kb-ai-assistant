"""
Scraper state management for tracking progress and enabling incremental crawling
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScraperStatus(str, Enum):
    """Scraper status enum"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


class CrawlState(BaseModel):
    """State of a crawling session"""
    session_id: str = Field(..., description="Unique session identifier")
    status: ScraperStatus = Field(default=ScraperStatus.IDLE, description="Current status")
    started_at: Optional[datetime] = Field(None, description="When scraping started")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    completed_at: Optional[datetime] = Field(None, description="When scraping completed")

    # Progress tracking
    total_threads_discovered: int = Field(default=0, description="Total threads found")
    threads_scraped: int = Field(default=0, description="Threads successfully scraped")
    threads_failed: int = Field(default=0, description="Threads that failed")
    messages_scraped: int = Field(default=0, description="Total messages scraped")

    # State tracking
    scraped_thread_ids: Set[str] = Field(default_factory=set, description="Already scraped thread IDs")
    failed_thread_ids: Set[str] = Field(default_factory=set, description="Failed thread IDs")
    pending_thread_urls: List[str] = Field(default_factory=list, description="URLs to scrape")

    # Incremental crawling
    last_scraped_date: Optional[datetime] = Field(None, description="Most recent message date")
    is_incremental: bool = Field(default=False, description="Incremental crawling mode")

    # Error tracking
    errors: List[str] = Field(default_factory=list, description="Error messages")
    last_error: Optional[str] = Field(None, description="Most recent error")

    # Configuration
    max_threads: Optional[int] = Field(None, description="Maximum threads to scrape")
    max_pages: Optional[int] = Field(None, description="Maximum pages to fetch")

    class Config:
        use_enum_values = True


class StateManager:
    """Manages scraper state persistence and recovery"""

    def __init__(self, state_dir: str = "./data/scraper_state"):
        """
        Initialize state manager

        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"StateManager initialized with state_dir: {state_dir}")

    def save_state(self, state: CrawlState):
        """
        Save crawl state to disk

        Args:
            state: CrawlState to save
        """
        state_file = self.state_dir / f"{state.session_id}.json"

        # Update timestamp
        state.updated_at = datetime.now()

        # Convert to dict and handle sets
        state_dict = state.model_dump()
        state_dict['scraped_thread_ids'] = list(state.scraped_thread_ids)
        state_dict['failed_thread_ids'] = list(state.failed_thread_ids)

        # Save to file
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, indent=2, default=str)

        logger.debug(f"Saved state for session {state.session_id}")

    def load_state(self, session_id: str) -> Optional[CrawlState]:
        """
        Load crawl state from disk

        Args:
            session_id: Session ID to load

        Returns:
            CrawlState or None if not found
        """
        state_file = self.state_dir / f"{session_id}.json"

        if not state_file.exists():
            logger.warning(f"State file not found for session {session_id}")
            return None

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state_dict = json.load(f)

            # Convert lists back to sets
            state_dict['scraped_thread_ids'] = set(state_dict.get('scraped_thread_ids', []))
            state_dict['failed_thread_ids'] = set(state_dict.get('failed_thread_ids', []))

            state = CrawlState(**state_dict)
            logger.info(f"Loaded state for session {session_id}")
            return state

        except Exception as e:
            logger.error(f"Error loading state for session {session_id}: {e}")
            return None

    def delete_state(self, session_id: str):
        """Delete state file"""
        state_file = self.state_dir / f"{session_id}.json"
        if state_file.exists():
            state_file.unlink()
            logger.info(f"Deleted state for session {session_id}")

    def list_sessions(self) -> List[str]:
        """List all session IDs"""
        return [f.stem for f in self.state_dir.glob("*.json")]

    def get_active_session(self) -> Optional[str]:
        """Get currently active session ID"""
        for session_id in self.list_sessions():
            state = self.load_state(session_id)
            if state and state.status in [ScraperStatus.RUNNING, ScraperStatus.PAUSED]:
                return session_id
        return None

    def create_checkpoint(self, state: CrawlState, checkpoint_name: str):
        """
        Create a named checkpoint of the current state

        Args:
            state: Current state
            checkpoint_name: Name for the checkpoint
        """
        checkpoint_file = self.state_dir / f"{state.session_id}_{checkpoint_name}.checkpoint.json"

        state_dict = state.model_dump()
        state_dict['scraped_thread_ids'] = list(state.scraped_thread_ids)
        state_dict['failed_thread_ids'] = list(state.failed_thread_ids)

        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, indent=2, default=str)

        logger.info(f"Created checkpoint '{checkpoint_name}' for session {state.session_id}")

    def restore_checkpoint(self, session_id: str, checkpoint_name: str) -> Optional[CrawlState]:
        """
        Restore state from a checkpoint

        Args:
            session_id: Session ID
            checkpoint_name: Checkpoint name

        Returns:
            Restored CrawlState or None
        """
        checkpoint_file = self.state_dir / f"{session_id}_{checkpoint_name}.checkpoint.json"

        if not checkpoint_file.exists():
            logger.warning(f"Checkpoint '{checkpoint_name}' not found for session {session_id}")
            return None

        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                state_dict = json.load(f)

            state_dict['scraped_thread_ids'] = set(state_dict.get('scraped_thread_ids', []))
            state_dict['failed_thread_ids'] = set(state_dict.get('failed_thread_ids', []))

            state = CrawlState(**state_dict)
            logger.info(f"Restored checkpoint '{checkpoint_name}' for session {session_id}")
            return state

        except Exception as e:
            logger.error(f"Error restoring checkpoint: {e}")
            return None
