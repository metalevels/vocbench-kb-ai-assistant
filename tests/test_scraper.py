"""
Tests for the scraper module
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from src.scraper.models import Message, Thread, ScraperStats
from src.scraper.google_groups_scraper import GoogleGroupsScraper


class TestModels:
    """Test data models"""

    def test_message_creation(self):
        """Test creating a Message object"""
        message = Message(
            message_id="msg_123",
            thread_id="thread_456",
            author="Test Author",
            author_email="test@example.com",
            date=datetime(2024, 1, 15, 10, 30),
            subject="Test Subject",
            body="Test message body",
            is_first_message=True,
            url="https://groups.google.com/test"
        )

        assert message.message_id == "msg_123"
        assert message.thread_id == "thread_456"
        assert message.author == "Test Author"
        assert message.is_first_message is True

    def test_thread_creation(self):
        """Test creating a Thread object"""
        messages = [
            Message(
                message_id="msg_1",
                thread_id="thread_1",
                author="Author 1",
                date=datetime(2024, 1, 15, 10, 30),
                subject="Test",
                body="First message",
                is_first_message=True,
                url="https://groups.google.com/test"
            ),
            Message(
                message_id="msg_2",
                thread_id="thread_1",
                author="Author 2",
                date=datetime(2024, 1, 15, 11, 30),
                subject="Re: Test",
                body="Reply message",
                is_first_message=False,
                url="https://groups.google.com/test"
            )
        ]

        thread = Thread(
            thread_id="thread_1",
            subject="Test Thread",
            first_message_date=messages[0].date,
            last_message_date=messages[1].date,
            message_count=len(messages),
            messages=messages,
            url="https://groups.google.com/test"
        )

        assert thread.thread_id == "thread_1"
        assert thread.message_count == 2
        assert len(thread.messages) == 2

    def test_scraper_stats(self):
        """Test ScraperStats model"""
        stats = ScraperStats(
            total_threads=10,
            total_messages=50,
            successful_threads=8,
            failed_threads=2,
            start_time=datetime(2024, 1, 15, 10, 0),
            end_time=datetime(2024, 1, 15, 10, 5)
        )

        assert stats.total_threads == 10
        assert stats.successful_threads == 8
        assert stats.duration_seconds == 300.0  # 5 minutes


class TestGoogleGroupsScraper:
    """Test GoogleGroupsScraper class"""

    def test_scraper_initialization(self, tmp_path):
        """Test scraper initialization"""
        scraper = GoogleGroupsScraper(
            group_url="https://groups.google.com/g/test-group",
            output_dir=str(tmp_path)
        )

        assert scraper.group_url == "https://groups.google.com/g/test-group"
        assert scraper.output_dir == tmp_path

    def test_extract_thread_id(self, tmp_path):
        """Test thread ID extraction from URL"""
        scraper = GoogleGroupsScraper(
            group_url="https://groups.google.com/g/test-group",
            output_dir=str(tmp_path)
        )

        url = "https://groups.google.com/g/vocbench-user/c/abc123xyz"
        thread_id = scraper._extract_thread_id(url)
        assert thread_id == "abc123xyz"

    def test_parse_date(self, tmp_path):
        """Test date parsing"""
        scraper = GoogleGroupsScraper(
            group_url="https://groups.google.com/g/test-group",
            output_dir=str(tmp_path)
        )

        # Test different date formats
        date1 = scraper._parse_date("01/15/24")
        assert date1 is not None
        assert date1.year == 2024

        date2 = scraper._parse_date("Jan 15, 2024")
        assert date2 is not None
        assert date2.month == 1

    def test_save_and_load_threads(self, tmp_path):
        """Test saving and loading threads"""
        scraper = GoogleGroupsScraper(
            group_url="https://groups.google.com/g/test-group",
            output_dir=str(tmp_path)
        )

        # Create test threads
        messages = [
            Message(
                message_id="msg_1",
                thread_id="thread_1",
                author="Author 1",
                date=datetime(2024, 1, 15, 10, 30),
                subject="Test",
                body="Test body",
                url="https://groups.google.com/test"
            )
        ]

        threads = [
            Thread(
                thread_id="thread_1",
                subject="Test Thread",
                first_message_date=messages[0].date,
                last_message_date=messages[0].date,
                message_count=1,
                messages=messages,
                url="https://groups.google.com/test"
            )
        ]

        # Save threads
        scraper.save_threads(threads, filename="test_output.json")

        # Load threads
        loaded_threads = scraper.load_threads(filename="test_output.json")

        assert len(loaded_threads) == 1
        assert loaded_threads[0].thread_id == "thread_1"
        assert loaded_threads[0].message_count == 1


@pytest.fixture
def sample_thread_data():
    """Fixture providing sample thread data"""
    return {
        "thread_id": "thread_123",
        "subject": "How to configure SPARQL endpoint?",
        "messages": [
            {
                "message_id": "msg_1",
                "thread_id": "thread_123",
                "author": "John Smith",
                "author_email": "john@example.com",
                "date": "2024-01-15T10:30:00",
                "subject": "How to configure SPARQL endpoint?",
                "body": "I'm trying to configure a custom SPARQL endpoint in VocBench. Can anyone help?",
                "is_first_message": True,
                "url": "https://groups.google.com/g/vocbench-user/c/thread_123"
            },
            {
                "message_id": "msg_2",
                "thread_id": "thread_123",
                "author": "Jane Doe",
                "author_email": "jane@example.com",
                "date": "2024-01-15T14:20:00",
                "subject": "Re: How to configure SPARQL endpoint?",
                "body": "You need to go to Settings > SPARQL and add your endpoint URL there.",
                "is_first_message": False,
                "url": "https://groups.google.com/g/vocbench-user/c/thread_123"
            }
        ]
    }
