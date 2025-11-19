"""
Gmail API authentication module.
"""
import json
from pathlib import Path
from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GmailAuthenticator:
    """Handles Gmail API authentication and service creation."""

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
        scopes: Optional[list[str]] = None
    ):
        """
        Initialize Gmail authenticator.

        Args:
            credentials_path: Path to OAuth credentials JSON file
            token_path: Path to store/load OAuth token
            scopes: List of OAuth scopes to request
        """
        self.credentials_path = credentials_path or settings.gmail_credentials_path
        self.token_path = token_path or settings.gmail_token_path
        self.scopes = scopes or settings.gmail_scopes
        self._creds: Optional[Credentials] = None
        self._service: Optional[Resource] = None

        logger.info(
            "gmail_authenticator_initialized",
            credentials_path=str(self.credentials_path),
            token_path=str(self.token_path),
            scopes=self.scopes
        )

    def _load_credentials(self) -> Optional[Credentials]:
        """
        Load credentials from token file if it exists.

        Returns:
            Credentials object or None
        """
        if not self.token_path.exists():
            logger.debug("token_file_not_found", path=str(self.token_path))
            return None

        try:
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                self.scopes
            )
            logger.info("credentials_loaded_from_token")
            return creds
        except Exception as e:
            logger.warning(
                "token_file_read_failed",
                error=str(e),
                path=str(self.token_path)
            )
            return None

    def _save_credentials(self, creds: Credentials) -> None:
        """
        Save credentials to token file.

        Args:
            creds: Credentials to save
        """
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as token_file:
                token_file.write(creds.to_json())
            logger.info("credentials_saved_to_token", path=str(self.token_path))
        except Exception as e:
            logger.error(
                "credentials_save_failed",
                error=str(e),
                path=str(self.token_path)
            )
            raise

    def _refresh_credentials(self, creds: Credentials) -> Credentials:
        """
        Refresh expired credentials.

        Args:
            creds: Credentials to refresh

        Returns:
            Refreshed credentials
        """
        try:
            creds.refresh(Request())
            logger.info("credentials_refreshed")
            self._save_credentials(creds)
            return creds
        except Exception as e:
            logger.error("credentials_refresh_failed", error=str(e))
            raise

    def _perform_oauth_flow(self) -> Credentials:
        """
        Perform OAuth flow to get new credentials.

        Returns:
            New credentials

        Raises:
            FileNotFoundError: If credentials file doesn't exist
            Exception: If OAuth flow fails
        """
        if not self.credentials_path.exists():
            error_msg = (
                f"Credentials file not found at {self.credentials_path}. "
                "Please download it from Google Cloud Console."
            )
            logger.error("credentials_file_not_found", path=str(self.credentials_path))
            raise FileNotFoundError(error_msg)

        try:
            logger.info("starting_oauth_flow")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                self.scopes
            )
            creds = flow.run_local_server(port=0)
            logger.info("oauth_flow_completed")
            self._save_credentials(creds)
            return creds
        except Exception as e:
            logger.error("oauth_flow_failed", error=str(e))
            raise

    def authenticate(self) -> Credentials:
        """
        Authenticate with Gmail API.

        Returns:
            Valid credentials

        Raises:
            FileNotFoundError: If credentials file doesn't exist
            Exception: If authentication fails
        """
        # Try to load existing credentials
        creds = self._load_credentials()

        # If no credentials or invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Try to refresh
                logger.info("credentials_expired_attempting_refresh")
                try:
                    creds = self._refresh_credentials(creds)
                except Exception:
                    # Refresh failed, need to re-authenticate
                    logger.warning("credentials_refresh_failed_reauthenticating")
                    creds = self._perform_oauth_flow()
            else:
                # No valid credentials, perform OAuth flow
                creds = self._perform_oauth_flow()

        self._creds = creds
        return creds

    def get_service(self, force_refresh: bool = False) -> Resource:
        """
        Get Gmail API service instance.

        Args:
            force_refresh: Force re-authentication

        Returns:
            Gmail API service

        Raises:
            Exception: If service creation fails
        """
        if force_refresh or not self._service:
            creds = self.authenticate()
            try:
                self._service = build('gmail', 'v1', credentials=creds)
                logger.info("gmail_service_created")
            except Exception as e:
                logger.error("gmail_service_creation_failed", error=str(e))
                raise

        return self._service

    def test_connection(self) -> bool:
        """
        Test Gmail API connection.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            service = self.get_service()
            # Try to get user profile as a simple test
            profile = service.users().getProfile(userId='me').execute()
            logger.info(
                "gmail_connection_test_successful",
                email_address=profile.get('emailAddress')
            )
            return True
        except HttpError as e:
            logger.error("gmail_connection_test_failed", error=str(e))
            return False
        except Exception as e:
            logger.error("gmail_connection_test_error", error=str(e))
            return False


# Global authenticator instance
_authenticator: Optional[GmailAuthenticator] = None


def get_gmail_service(force_refresh: bool = False) -> Resource:
    """
    Get Gmail API service (singleton pattern).

    Args:
        force_refresh: Force re-authentication

    Returns:
        Gmail API service
    """
    global _authenticator
    if _authenticator is None:
        _authenticator = GmailAuthenticator()
    return _authenticator.get_service(force_refresh=force_refresh)


def test_gmail_connection() -> bool:
    """
    Test Gmail API connection.

    Returns:
        True if successful, False otherwise
    """
    global _authenticator
    if _authenticator is None:
        _authenticator = GmailAuthenticator()
    return _authenticator.test_connection()
