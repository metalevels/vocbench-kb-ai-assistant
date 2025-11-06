"""
Queue-based scraper manager with start/stop/pause/resume controls
"""
import logging
import threading
import time
import uuid
from datetime import datetime
from queue import Queue, Empty
from typing import Optional, Dict, Any, Callable

from src.scraper.google_groups_scraper import GoogleGroupsScraper
from src.scraper.state import CrawlState, StateManager, ScraperStatus
from src.scraper.models import Thread

logger = logging.getLogger(__name__)


class ScraperManager:
    """
    Manages scraping operations with queue-based architecture
    Supports start/stop/pause/resume and incremental crawling
    """

    def __init__(
        self,
        scraper: GoogleGroupsScraper,
        state_manager: Optional[StateManager] = None,
        max_workers: int = 1,
        checkpoint_interval: int = 10
    ):
        """
        Initialize scraper manager

        Args:
            scraper: GoogleGroupsScraper instance
            state_manager: StateManager for persistence
            max_workers: Number of concurrent workers (future enhancement)
            checkpoint_interval: Save state every N threads
        """
        self.scraper = scraper
        self.state_manager = state_manager or StateManager()
        self.max_workers = max_workers
        self.checkpoint_interval = checkpoint_interval

        # Threading
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

        # Queue
        self.url_queue: Queue = Queue()

        # Current state
        self.current_state: Optional[CrawlState] = None

        # Callbacks
        self.on_thread_scraped: Optional[Callable[[Thread], None]] = None
        self.on_progress_update: Optional[Callable[[CrawlState], None]] = None

        logger.info("ScraperManager initialized")

    def start_scraping(
        self,
        max_threads: Optional[int] = None,
        max_pages: Optional[int] = None,
        incremental: bool = False,
        session_id: Optional[str] = None
    ) -> str:
        """
        Start a new scraping session

        Args:
            max_threads: Maximum threads to scrape
            max_pages: Maximum pages to fetch
            incremental: Enable incremental mode (only new content)
            session_id: Resume existing session or create new

        Returns:
            Session ID
        """
        # Check if already running
        if self.current_state and self.current_state.status == ScraperStatus.RUNNING:
            raise RuntimeError("Scraper is already running")

        # Load or create state
        if session_id:
            self.current_state = self.state_manager.load_state(session_id)
            if not self.current_state:
                raise ValueError(f"Session {session_id} not found")
            logger.info(f"Resuming session {session_id}")
        else:
            session_id = str(uuid.uuid4())
            self.current_state = CrawlState(
                session_id=session_id,
                max_threads=max_threads,
                max_pages=max_pages,
                is_incremental=incremental
            )
            logger.info(f"Created new session {session_id}")

        # Update state
        self.current_state.status = ScraperStatus.RUNNING
        self.current_state.started_at = datetime.now()

        # Reset threading events
        self.stop_event.clear()
        self.pause_event.clear()

        # Discover thread URLs if not resuming
        if not self.current_state.pending_thread_urls:
            self._discover_threads()

        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        logger.info(f"Scraping started for session {session_id}")
        return session_id

    def stop_scraping(self):
        """Stop scraping gracefully"""
        if not self.current_state or self.current_state.status != ScraperStatus.RUNNING:
            logger.warning("No active scraping session to stop")
            return

        logger.info(f"Stopping session {self.current_state.session_id}")
        self.stop_event.set()

        # Wait for worker to finish
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

        self.current_state.status = ScraperStatus.STOPPED
        self.state_manager.save_state(self.current_state)
        logger.info("Scraping stopped")

    def pause_scraping(self):
        """Pause scraping"""
        if not self.current_state or self.current_state.status != ScraperStatus.RUNNING:
            logger.warning("No active scraping session to pause")
            return

        logger.info(f"Pausing session {self.current_state.session_id}")
        self.pause_event.set()
        self.current_state.status = ScraperStatus.PAUSED
        self.state_manager.save_state(self.current_state)
        logger.info("Scraping paused")

    def resume_scraping(self):
        """Resume paused scraping"""
        if not self.current_state or self.current_state.status != ScraperStatus.PAUSED:
            logger.warning("No paused session to resume")
            return

        logger.info(f"Resuming session {self.current_state.session_id}")
        self.pause_event.clear()
        self.current_state.status = ScraperStatus.RUNNING
        self.state_manager.save_state(self.current_state)
        logger.info("Scraping resumed")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current scraping status

        Returns:
            Status dictionary
        """
        if not self.current_state:
            return {
                "status": "no_active_session",
                "session_id": None
            }

        progress = 0.0
        if self.current_state.total_threads_discovered > 0:
            progress = (self.current_state.threads_scraped /
                       self.current_state.total_threads_discovered) * 100

        return {
            "session_id": self.current_state.session_id,
            "status": self.current_state.status,
            "started_at": self.current_state.started_at.isoformat() if self.current_state.started_at else None,
            "progress": {
                "percentage": round(progress, 2),
                "threads_scraped": self.current_state.threads_scraped,
                "threads_failed": self.current_state.threads_failed,
                "total_threads": self.current_state.total_threads_discovered,
                "messages_scraped": self.current_state.messages_scraped,
                "pending": len(self.current_state.pending_thread_urls)
            },
            "is_incremental": self.current_state.is_incremental,
            "last_error": self.current_state.last_error,
            "errors_count": len(self.current_state.errors)
        }

    def _discover_threads(self):
        """Discover thread URLs to scrape"""
        logger.info("Discovering thread URLs...")

        try:
            thread_urls = self.scraper.get_thread_urls(
                max_pages=self.current_state.max_pages
            )

            # Filter already scraped threads
            if self.current_state.is_incremental:
                thread_urls = [
                    url for url in thread_urls
                    if self.scraper._extract_thread_id(url) not in self.current_state.scraped_thread_ids
                ]
                logger.info(f"Incremental mode: {len(thread_urls)} new threads to scrape")

            # Apply max_threads limit
            if self.current_state.max_threads:
                thread_urls = thread_urls[:self.current_state.max_threads]

            self.current_state.pending_thread_urls = thread_urls
            self.current_state.total_threads_discovered = len(thread_urls)

            logger.info(f"Discovered {len(thread_urls)} threads to scrape")

        except Exception as e:
            logger.error(f"Error discovering threads: {e}")
            self.current_state.status = ScraperStatus.ERROR
            self.current_state.last_error = str(e)
            raise

    def _worker_loop(self):
        """Main worker loop"""
        logger.info("Worker thread started")

        try:
            while self.current_state.pending_thread_urls and not self.stop_event.is_set():
                # Check for pause
                while self.pause_event.is_set() and not self.stop_event.is_set():
                    time.sleep(0.5)

                if self.stop_event.is_set():
                    break

                # Get next URL
                url = self.current_state.pending_thread_urls.pop(0)

                # Scrape thread
                try:
                    thread = self.scraper.scrape_thread(url)

                    if thread:
                        # Update state
                        self.current_state.threads_scraped += 1
                        self.current_state.messages_scraped += thread.message_count
                        self.current_state.scraped_thread_ids.add(thread.thread_id)

                        # Update last scraped date
                        if thread.last_message_date:
                            if (not self.current_state.last_scraped_date or
                                thread.last_message_date > self.current_state.last_scraped_date):
                                self.current_state.last_scraped_date = thread.last_message_date

                        # Callback
                        if self.on_thread_scraped:
                            self.on_thread_scraped(thread)

                        logger.info(f"Scraped thread {thread.thread_id}: {thread.message_count} messages")
                    else:
                        self.current_state.threads_failed += 1
                        thread_id = self.scraper._extract_thread_id(url)
                        if thread_id:
                            self.current_state.failed_thread_ids.add(thread_id)

                except Exception as e:
                    logger.error(f"Error scraping thread {url}: {e}")
                    self.current_state.threads_failed += 1
                    self.current_state.errors.append(f"{url}: {str(e)}")
                    self.current_state.last_error = str(e)

                # Checkpoint periodically
                if self.current_state.threads_scraped % self.checkpoint_interval == 0:
                    self.state_manager.save_state(self.current_state)
                    logger.info(f"Checkpoint saved at {self.current_state.threads_scraped} threads")

                # Progress callback
                if self.on_progress_update:
                    self.on_progress_update(self.current_state)

            # Final state
            if not self.stop_event.is_set():
                self.current_state.status = ScraperStatus.COMPLETED
                self.current_state.completed_at = datetime.now()
                logger.info("Scraping completed successfully")

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            self.current_state.status = ScraperStatus.ERROR
            self.current_state.last_error = str(e)

        finally:
            # Save final state
            self.state_manager.save_state(self.current_state)
            logger.info("Worker thread finished")

    def retry_failed_threads(self):
        """Retry all failed threads"""
        if not self.current_state:
            raise RuntimeError("No active session")

        if not self.current_state.failed_thread_ids:
            logger.info("No failed threads to retry")
            return

        logger.info(f"Retrying {len(self.current_state.failed_thread_ids)} failed threads")

        # Reconstruct URLs from failed thread IDs (this is a simplification)
        # In production, you'd store the full URLs
        failed_urls = []
        for thread_id in self.current_state.failed_thread_ids:
            url = f"{self.scraper.group_url}/c/{thread_id}"
            failed_urls.append(url)

        # Add back to pending
        self.current_state.pending_thread_urls.extend(failed_urls)
        self.current_state.failed_thread_ids.clear()
        self.current_state.threads_failed = 0

        self.state_manager.save_state(self.current_state)
        logger.info("Failed threads added back to queue")

    def list_sessions(self) -> Dict[str, Any]:
        """List all scraping sessions"""
        sessions = []
        for session_id in self.state_manager.list_sessions():
            state = self.state_manager.load_state(session_id)
            if state:
                sessions.append({
                    "session_id": session_id,
                    "status": state.status,
                    "started_at": state.started_at.isoformat() if state.started_at else None,
                    "threads_scraped": state.threads_scraped,
                    "total_threads": state.total_threads_discovered,
                    "is_incremental": state.is_incremental
                })

        return {"sessions": sessions, "total": len(sessions)}
