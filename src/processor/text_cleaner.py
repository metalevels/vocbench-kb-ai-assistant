"""
Text cleaning and normalization utilities
"""
import re
import logging
from typing import List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TextCleaner:
    """Cleans and normalizes text from scraped messages"""

    def __init__(self):
        # Common email signatures patterns
        self.signature_patterns = [
            r'--\s*\n.*',  # Standard email signature
            r'Best regards,.*',
            r'Thanks,.*',
            r'Regards,.*',
            r'Sent from my.*',
            r'Get Outlook for.*',
        ]

        # URL pattern
        self.url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

        # Email pattern
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    def clean_html(self, text: str) -> str:
        """
        Remove HTML tags and entities

        Args:
            text: Raw text potentially containing HTML

        Returns:
            Cleaned text
        """
        soup = BeautifulSoup(text, 'html.parser')

        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    def remove_signatures(self, text: str) -> str:
        """
        Remove common email signatures

        Args:
            text: Text potentially containing signatures

        Returns:
            Text with signatures removed
        """
        for pattern in self.signature_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

        return text.strip()

    def normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace (multiple spaces, tabs, newlines)

        Args:
            text: Text with irregular whitespace

        Returns:
            Normalized text
        """
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)

        # Replace multiple newlines with double newline
        text = re.sub(r'\n\s*\n+', '\n\n', text)

        # Remove trailing/leading whitespace
        text = text.strip()

        return text

    def remove_quoted_text(self, text: str) -> str:
        """
        Remove quoted text from email replies (lines starting with >)

        Args:
            text: Email text potentially containing quotes

        Returns:
            Text with quotes removed
        """
        lines = text.split('\n')
        non_quoted_lines = [line for line in lines if not line.strip().startswith('>')]
        return '\n'.join(non_quoted_lines)

    def anonymize_emails(self, text: str, replacement: str = '[EMAIL]') -> str:
        """
        Replace email addresses with placeholder

        Args:
            text: Text containing emails
            replacement: Replacement string

        Returns:
            Text with emails anonymized
        """
        return re.sub(self.email_pattern, replacement, text)

    def shorten_urls(self, text: str, replacement: str = '[URL]') -> str:
        """
        Replace URLs with placeholder

        Args:
            text: Text containing URLs
            replacement: Replacement string

        Returns:
            Text with URLs replaced
        """
        return re.sub(self.url_pattern, replacement, text)

    def clean(
        self,
        text: str,
        remove_html: bool = True,
        remove_sigs: bool = True,
        remove_quotes: bool = True,
        anonymize_email: bool = True,
        shorten_url: bool = False
    ) -> str:
        """
        Apply all cleaning steps

        Args:
            text: Raw text to clean
            remove_html: Remove HTML tags
            remove_sigs: Remove email signatures
            remove_quotes: Remove quoted text
            anonymize_email: Replace emails with placeholder
            shorten_url: Replace URLs with placeholder

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove HTML
        if remove_html:
            text = self.clean_html(text)

        # Remove quoted text
        if remove_quotes:
            text = self.remove_quoted_text(text)

        # Remove signatures
        if remove_sigs:
            text = self.remove_signatures(text)

        # Anonymize emails
        if anonymize_email:
            text = self.anonymize_emails(text)

        # Shorten URLs
        if shorten_url:
            text = self.shorten_urls(text)

        # Normalize whitespace
        text = self.normalize_whitespace(text)

        return text

    def clean_batch(self, texts: List[str], **kwargs) -> List[str]:
        """
        Clean multiple texts

        Args:
            texts: List of texts to clean
            **kwargs: Arguments to pass to clean()

        Returns:
            List of cleaned texts
        """
        return [self.clean(text, **kwargs) for text in texts]
