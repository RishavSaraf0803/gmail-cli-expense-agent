"""
Gmail client for fetching and processing emails with batch processing and rate limiting.
"""
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator
from googleapiclient.errors import HttpError
from googleapiclient.discovery import Resource

from fincli.auth.gmail_auth import get_gmail_service
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GmailClientError(Exception):
    """Custom exception for Gmail client errors."""
    pass


class EmailMessage:
    """Represents an email message with relevant metadata."""

    def __init__(
        self,
        message_id: str,
        subject: str,
        date: str,
        snippet: str,
        full_content: Optional[str] = None
    ):
        """
        Initialize email message.

        Args:
            message_id: Gmail message ID
            subject: Email subject
            date: Email date
            snippet: Email snippet
            full_content: Full email content (optional)
        """
        self.message_id = message_id
        self.subject = subject
        self.date = date
        self.snippet = snippet
        self.full_content = full_content

    def get_context_text(self) -> str:
        """
        Get combined text for LLM context.

        Returns:
            Formatted text for processing
        """
        return f"Subject: {self.subject}\nDate: {self.date}\nContent: {self.snippet}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "subject": self.subject,
            "date": self.date,
            "snippet": self.snippet,
            "full_content": self.full_content
        }


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(
        self,
        service: Optional[Resource] = None,
        max_results: Optional[int] = None,
        batch_size: Optional[int] = None
    ):
        """
        Initialize Gmail client.

        Args:
            service: Gmail API service (optional, will be created if not provided)
            max_results: Maximum results per query
            batch_size: Batch size for processing
        """
        self.service = service or get_gmail_service()
        self.max_results = max_results or settings.gmail_max_results
        self.batch_size = batch_size or settings.batch_size

        logger.info(
            "gmail_client_initialized",
            max_results=self.max_results,
            batch_size=self.batch_size
        )

    def _get_header_value(self, headers: List[Dict[str, str]], name: str) -> str:
        """
        Extract header value by name.

        Args:
            headers: List of header dictionaries
            name: Header name to find

        Returns:
            Header value or "Unknown" if not found
        """
        for header in headers:
            if header.get('name', '').lower() == name.lower():
                return header.get('value', 'Unknown')
        return 'Unknown'

    def _parse_message(self, message: Dict[str, Any]) -> EmailMessage:
        """
        Parse Gmail API message into EmailMessage object.

        Args:
            message: Raw message from Gmail API

        Returns:
            EmailMessage object
        """
        message_id = message.get('id', '')
        snippet = message.get('snippet', '')
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        subject = self._get_header_value(headers, 'Subject')
        date = self._get_header_value(headers, 'Date')

        return EmailMessage(
            message_id=message_id,
            subject=subject,
            date=date,
            snippet=snippet
        )

    def fetch_messages(
        self,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
        label_ids: Optional[List[str]] = None
    ) -> List[EmailMessage]:
        """
        Fetch messages from Gmail.

        Args:
            query: Gmail search query
            max_results: Maximum number of messages to fetch
            label_ids: Label IDs to filter by

        Returns:
            List of EmailMessage objects

        Raises:
            GmailClientError: If fetching fails
        """
        query = query or settings.email_query
        max_results = max_results or self.max_results

        logger.info(
            "fetching_messages",
            query=query,
            max_results=max_results
        )

        try:
            # First, list messages
            list_params = {
                'userId': 'me',
                'q': query,
                'maxResults': max_results
            }
            if label_ids:
                list_params['labelIds'] = label_ids

            results = self.service.users().messages().list(**list_params).execute()
            message_list = results.get('messages', [])

            if not message_list:
                logger.info("no_messages_found", query=query)
                return []

            logger.info("messages_listed", count=len(message_list))

            # Fetch full messages in batches
            messages = []
            for i in range(0, len(message_list), self.batch_size):
                batch = message_list[i:i + self.batch_size]
                for msg_info in batch:
                    try:
                        msg = self.service.users().messages().get(
                            userId='me',
                            id=msg_info['id'],
                            format='metadata',
                            metadataHeaders=['Subject', 'Date']
                        ).execute()
                        messages.append(self._parse_message(msg))
                    except HttpError as e:
                        logger.warning(
                            "message_fetch_failed",
                            message_id=msg_info['id'],
                            error=str(e)
                        )
                        continue

                # Rate limiting - small delay between batches
                if i + self.batch_size < len(message_list):
                    time.sleep(0.1)

            logger.info("messages_fetched", count=len(messages))
            return messages

        except HttpError as e:
            error_msg = f"Gmail API error: {e}"
            logger.error("gmail_api_error", error=str(e))
            raise GmailClientError(error_msg)
        except Exception as e:
            error_msg = f"Failed to fetch messages: {e}"
            logger.error("message_fetch_failed", error=str(e))
            raise GmailClientError(error_msg)

    def fetch_messages_stream(
        self,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
        label_ids: Optional[List[str]] = None
    ) -> Generator[EmailMessage, None, None]:
        """
        Fetch messages as a generator for memory efficiency.

        Args:
            query: Gmail search query
            max_results: Maximum number of messages to fetch
            label_ids: Label IDs to filter by

        Yields:
            EmailMessage objects

        Raises:
            GmailClientError: If fetching fails
        """
        query = query or settings.email_query
        max_results = max_results or self.max_results

        logger.info(
            "streaming_messages",
            query=query,
            max_results=max_results
        )

        try:
            # List messages
            list_params = {
                'userId': 'me',
                'q': query,
                'maxResults': max_results
            }
            if label_ids:
                list_params['labelIds'] = label_ids

            results = self.service.users().messages().list(**list_params).execute()
            message_list = results.get('messages', [])

            if not message_list:
                logger.info("no_messages_found", query=query)
                return

            logger.info("messages_listed_for_stream", count=len(message_list))

            # Stream messages
            for i, msg_info in enumerate(message_list):
                try:
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_info['id'],
                        format='metadata',
                        metadataHeaders=['Subject', 'Date']
                    ).execute()
                    yield self._parse_message(msg)

                    # Rate limiting
                    if (i + 1) % self.batch_size == 0:
                        time.sleep(0.1)

                except HttpError as e:
                    logger.warning(
                        "message_stream_fetch_failed",
                        message_id=msg_info['id'],
                        error=str(e)
                    )
                    continue

        except HttpError as e:
            error_msg = f"Gmail API error: {e}"
            logger.error("gmail_api_error_stream", error=str(e))
            raise GmailClientError(error_msg)
        except Exception as e:
            error_msg = f"Failed to stream messages: {e}"
            logger.error("message_stream_failed", error=str(e))
            raise GmailClientError(error_msg)

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get user's Gmail profile.

        Returns:
            User profile dictionary

        Raises:
            GmailClientError: If profile fetch fails
        """
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            logger.info(
                "user_profile_fetched",
                email=profile.get('emailAddress')
            )
            return profile
        except HttpError as e:
            error_msg = f"Failed to get user profile: {e}"
            logger.error("user_profile_fetch_failed", error=str(e))
            raise GmailClientError(error_msg)


# Global client instance
_gmail_client: Optional[GmailClient] = None


def get_gmail_client() -> GmailClient:
    """
    Get Gmail client (singleton pattern).

    Returns:
        GmailClient instance
    """
    global _gmail_client
    if _gmail_client is None:
        _gmail_client = GmailClient()
    return _gmail_client
