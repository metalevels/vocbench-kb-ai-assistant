"""
API routes for scraper management
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.scraper.google_groups_scraper import GoogleGroupsScraper
from src.scraper.manager import ScraperManager
from src.scraper.state import StateManager
from src.scraper.models import Thread
from src.processor.processor import DataProcessor
from config.settings import settings

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/scraper", tags=["Scraper"])

# Global scraper manager (initialized on first use)
_scraper_manager: Optional[ScraperManager] = None


def get_scraper_manager() -> ScraperManager:
    """Get or create scraper manager instance"""
    global _scraper_manager

    if _scraper_manager is None:
        scraper = GoogleGroupsScraper(
            group_url=settings.google_group_url,
            user_agent=settings.scraper_user_agent,
            output_dir="./data/raw"
        )
        state_manager = StateManager(state_dir="./data/scraper_state")
        _scraper_manager = ScraperManager(
            scraper=scraper,
            state_manager=state_manager,
            checkpoint_interval=10
        )
        logger.info("ScraperManager initialized")

    return _scraper_manager


# Request/Response Models
class StartScrapingRequest(BaseModel):
    """Request to start scraping"""
    max_threads: Optional[int] = Field(None, description="Maximum threads to scrape")
    max_pages: Optional[int] = Field(None, description="Maximum pages to fetch")
    incremental: bool = Field(False, description="Enable incremental mode (only new content)")
    auto_process: bool = Field(False, description="Automatically process and index scraped data")


class StartScrapingResponse(BaseModel):
    """Response from start scraping"""
    session_id: str = Field(..., description="Scraping session ID")
    status: str = Field(..., description="Current status")
    message: str = Field(..., description="Status message")


class ScraperStatusResponse(BaseModel):
    """Scraper status response"""
    session_id: Optional[str]
    status: str
    started_at: Optional[str]
    progress: dict
    is_incremental: bool
    last_error: Optional[str]
    errors_count: int


class SessionsResponse(BaseModel):
    """List of scraping sessions"""
    sessions: list
    total: int


# Endpoints
@router.post("/start", response_model=StartScrapingResponse)
async def start_scraping(request: StartScrapingRequest, background_tasks: BackgroundTasks):
    """
    Start a new scraping session

    This will begin scraping the VocBench Google Group in the background.
    Use the returned session_id to monitor progress.
    """
    try:
        manager = get_scraper_manager()

        # Setup auto-processing callback if requested
        if request.auto_process:
            def on_thread_scraped(thread: Thread):
                """Auto-process scraped threads"""
                try:
                    # This would trigger processing pipeline
                    logger.info(f"Auto-processing thread {thread.thread_id}")
                except Exception as e:
                    logger.error(f"Auto-processing error: {e}")

            manager.on_thread_scraped = on_thread_scraped

        # Start scraping
        session_id = manager.start_scraping(
            max_threads=request.max_threads,
            max_pages=request.max_pages,
            incremental=request.incremental
        )

        return StartScrapingResponse(
            session_id=session_id,
            status="running",
            message=f"Scraping started with session ID: {session_id}"
        )

    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_scraping():
    """
    Stop the current scraping session gracefully

    This will save the current state and can be resumed later.
    """
    try:
        manager = get_scraper_manager()
        manager.stop_scraping()

        return {
            "status": "stopped",
            "message": "Scraping stopped successfully"
        }

    except Exception as e:
        logger.error(f"Error stopping scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause")
async def pause_scraping():
    """
    Pause the current scraping session

    The scraper will pause after completing the current thread.
    Use /scraper/resume to continue.
    """
    try:
        manager = get_scraper_manager()
        manager.pause_scraping()

        return {
            "status": "paused",
            "message": "Scraping paused successfully"
        }

    except Exception as e:
        logger.error(f"Error pausing scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
async def resume_scraping():
    """
    Resume a paused scraping session

    Continues from where the scraper was paused.
    """
    try:
        manager = get_scraper_manager()
        manager.resume_scraping()

        return {
            "status": "running",
            "message": "Scraping resumed successfully"
        }

    except Exception as e:
        logger.error(f"Error resuming scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=ScraperStatusResponse)
async def get_scraper_status():
    """
    Get current scraper status and progress

    Returns detailed information about the current or most recent scraping session.
    """
    try:
        manager = get_scraper_manager()
        status = manager.get_status()

        return ScraperStatusResponse(**status)

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionsResponse)
async def list_sessions():
    """
    List all scraping sessions

    Returns a list of all past and current scraping sessions.
    """
    try:
        manager = get_scraper_manager()
        sessions = manager.list_sessions()

        return SessionsResponse(**sessions)

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """
    Resume a specific session by ID

    This allows you to resume scraping from a previous session.
    """
    try:
        manager = get_scraper_manager()

        # Stop current if running
        if manager.current_state and manager.current_state.status == "running":
            manager.stop_scraping()

        # Start with specific session
        resumed_session_id = manager.start_scraping(session_id=session_id)

        return {
            "session_id": resumed_session_id,
            "status": "running",
            "message": f"Session {session_id} resumed successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error resuming session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry-failed")
async def retry_failed():
    """
    Retry all failed threads in the current session

    Re-adds all failed threads back to the queue for another attempt.
    """
    try:
        manager = get_scraper_manager()
        manager.retry_failed_threads()

        return {
            "status": "success",
            "message": "Failed threads added back to queue"
        }

    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrying failed threads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a scraping session

    Removes the session state file. Cannot be undone.
    """
    try:
        manager = get_scraper_manager()
        manager.state_manager.delete_state(session_id)

        return {
            "status": "deleted",
            "message": f"Session {session_id} deleted successfully"
        }

    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
