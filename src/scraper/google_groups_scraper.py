"""
Google Groups scraper for extracting public discussion threads
"""
import re
import json
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from src.scraper.models import Message, Thread, ScraperStats

logger = logging.getLogger(__name__)


class GoogleGroupsScraper:
    """Scraper for extracting threads and messages from Google Groups"""

    def __init__(
        self,
        group_url: str,
        user_agent: str = "VocBenchBot/1.0",
        rate_limit_delay: float = 1.0,
        output_dir: str = "./data/raw"
    ):
        """
        Initialize the scraper

        Args:
            group_url: Base URL of the Google Group
            user_agent: User agent string for requests
            rate_limit_delay: Delay between requests in seconds
            output_dir: Directory to save scraped data
        """
        self.group_url = group_url.rstrip('/')
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        self.stats = ScraperStats()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_page(self, url: str) -> str:
        """
        Fetch a page with retry logic

        Args:
            url: URL to fetch

        Returns:
            HTML content of the page
        """
        logger.info(f"Fetching: {url}")
        time.sleep(self.rate_limit_delay)

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """
        Parse various date formats from Google Groups

        Args:
            date_string: Date string to parse

        Returns:
            Parsed datetime or None if parsing fails
        """
        # Common date formats in Google Groups
        formats = [
            "%m/%d/%y",  # 01/15/24
            "%b %d, %Y",  # Jan 15, 2024
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format
            "%a, %d %b %Y %H:%M:%S %Z",  # RFC 2822
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_string.strip(), fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_string}")
        return None

    def get_thread_urls(self, max_pages: Optional[int] = None) -> List[str]:
        """
        Get all thread URLs from the group

        Args:
            max_pages: Maximum number of pages to scrape (None for all)

        Returns:
            List of thread URLs
        """
        thread_urls = []
        page_num = 0

        while True:
            if max_pages and page_num >= max_pages:
                break

            # Google Groups URL structure
            list_url = f"{self.group_url}/topics"
            if page_num > 0:
                list_url += f"?start={page_num * 20}"  # Typically 20 threads per page

            try:
                html = self._fetch_page(list_url)
                soup = BeautifulSoup(html, 'lxml')

                # Find thread links - this selector may need adjustment based on actual HTML
                links = soup.select('a[href*="/g/"][href*="/c/"]')

                if not links:
                    logger.info(f"No more threads found on page {page_num}")
                    break

                for link in links:
                    href = link.get('href')
                    if href and '/c/' in href:
                        full_url = urljoin(self.group_url, href)
                        if full_url not in thread_urls:
                            thread_urls.append(full_url)

                page_num += 1
                logger.info(f"Found {len(links)} threads on page {page_num}")

            except Exception as e:
                logger.error(f"Error fetching thread list page {page_num}: {e}")
                self.stats.errors.append(f"Thread list page {page_num}: {str(e)}")
                break

        logger.info(f"Total thread URLs found: {len(thread_urls)}")
        return thread_urls

    def scrape_thread(self, thread_url: str) -> Optional[Thread]:
        """
        Scrape a single thread and all its messages

        Args:
            thread_url: URL of the thread

        Returns:
            Thread object with all messages, or None if scraping fails
        """
        try:
            html = self._fetch_page(thread_url)
            soup = BeautifulSoup(html, 'lxml')

            # Extract thread ID from URL
            thread_id = self._extract_thread_id(thread_url)
            if not thread_id:
                logger.error(f"Could not extract thread ID from {thread_url}")
                return None

            # Extract thread subject
            subject_elem = soup.find('h1') or soup.find('title')
            subject = subject_elem.get_text(strip=True) if subject_elem else "Unknown Subject"

            messages = []
            message_elems = soup.find_all('div', {'data-message-id': True})

            # If no messages found with data-message-id, try alternative selectors
            if not message_elems:
                message_elems = soup.find_all('div', class_=re.compile(r'message|post|comment', re.I))

            for idx, msg_elem in enumerate(message_elems):
                message = self._parse_message(msg_elem, thread_id, thread_url, idx == 0)
                if message:
                    messages.append(message)

            if not messages:
                logger.warning(f"No messages found in thread {thread_url}")
                return None

            # Create thread object
            messages.sort(key=lambda m: m.date)
            thread = Thread(
                thread_id=thread_id,
                subject=subject,
                first_message_date=messages[0].date,
                last_message_date=messages[-1].date,
                message_count=len(messages),
                messages=messages,
                url=thread_url
            )

            self.stats.successful_threads += 1
            return thread

        except Exception as e:
            logger.error(f"Error scraping thread {thread_url}: {e}")
            self.stats.errors.append(f"Thread {thread_url}: {str(e)}")
            self.stats.failed_threads += 1
            return None

    def _extract_thread_id(self, url: str) -> Optional[str]:
        """Extract thread ID from URL"""
        match = re.search(r'/c/([^/]+)', url)
        return match.group(1) if match else None

    def _parse_message(
        self,
        elem: BeautifulSoup,
        thread_id: str,
        thread_url: str,
        is_first: bool
    ) -> Optional[Message]:
        """
        Parse a message element

        Args:
            elem: BeautifulSoup element containing the message
            thread_id: ID of the parent thread
            thread_url: URL of the thread
            is_first: Whether this is the first message in the thread

        Returns:
            Message object or None if parsing fails
        """
        try:
            # Extract message ID
            message_id = elem.get('data-message-id') or elem.get('id') or f"msg_{hash(elem.get_text()[:100])}"

            # Extract author
            author_elem = elem.find('span', class_=re.compile(r'author|name', re.I))
            author = author_elem.get_text(strip=True) if author_elem else "Unknown"

            # Extract email if available
            email_elem = elem.find('a', href=re.compile(r'mailto:'))
            author_email = email_elem.get('href').replace('mailto:', '') if email_elem else None

            # Extract date
            date_elem = elem.find('time') or elem.find('span', class_=re.compile(r'date|time', re.I))
            date_str = date_elem.get('datetime') or date_elem.get_text(strip=True) if date_elem else ""
            date = self._parse_date(date_str) or datetime.now()

            # Extract body
            body_elem = elem.find('div', class_=re.compile(r'body|content|message', re.I))
            body = body_elem.get_text(strip=True) if body_elem else elem.get_text(strip=True)

            # Extract subject (for first message, use thread subject)
            subject_elem = elem.find('h3') or elem.find('div', class_=re.compile(r'subject|title', re.I))
            subject = subject_elem.get_text(strip=True) if subject_elem else "Re: Discussion"

            return Message(
                message_id=message_id,
                thread_id=thread_id,
                author=author,
                author_email=author_email,
                date=date,
                subject=subject,
                body=body,
                is_first_message=is_first,
                reply_to=None,  # Can be enhanced with reply tracking
                url=thread_url
            )

        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None

    def scrape_all(self, max_threads: Optional[int] = None, max_pages: Optional[int] = None) -> List[Thread]:
        """
        Scrape all threads from the group

        Args:
            max_threads: Maximum number of threads to scrape (None for all)
            max_pages: Maximum number of thread list pages to fetch

        Returns:
            List of Thread objects
        """
        self.stats = ScraperStats()
        self.stats.start_time = datetime.now()

        logger.info(f"Starting scrape of {self.group_url}")

        # Get all thread URLs
        thread_urls = self.get_thread_urls(max_pages=max_pages)
        self.stats.total_threads = len(thread_urls)

        if max_threads:
            thread_urls = thread_urls[:max_threads]

        threads = []
        for idx, url in enumerate(thread_urls, 1):
            logger.info(f"Scraping thread {idx}/{len(thread_urls)}: {url}")
            thread = self.scrape_thread(url)
            if thread:
                threads.append(thread)
                self.stats.total_messages += thread.message_count

        self.stats.end_time = datetime.now()
        logger.info(f"Scraping complete. Processed {len(threads)} threads with {self.stats.total_messages} messages")

        return threads

    def save_threads(self, threads: List[Thread], filename: str = "scraped_data.json"):
        """
        Save threads to JSON file

        Args:
            threads: List of Thread objects
            filename: Output filename
        """
        output_path = self.output_dir / filename

        data = {
            "scraped_at": datetime.now().isoformat(),
            "group_url": self.group_url,
            "stats": self.stats.model_dump(),
            "threads": [thread.model_dump() for thread in threads]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Saved {len(threads)} threads to {output_path}")

    def load_threads(self, filename: str = "scraped_data.json") -> List[Thread]:
        """
        Load threads from JSON file

        Args:
            filename: Input filename

        Returns:
            List of Thread objects
        """
        input_path = self.output_dir / filename

        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        threads = [Thread(**thread_data) for thread_data in data.get('threads', [])]
        logger.info(f"Loaded {len(threads)} threads from {input_path}")

        return threads
