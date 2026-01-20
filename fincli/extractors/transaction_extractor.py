"""
Transaction extractor for parsing financial data from emails using LLM.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from dateutil import parser as date_parser

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.clients.llm_factory import get_llm_client, LLMClientError
from fincli.clients.gmail_client import EmailMessage
from fincli.prompts.prompt_manager import get_prompt_manager
from fincli.cache.llm_cache import LLMCache
from fincli.utils.logger import get_logger
from fincli.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class TransactionExtractorError(Exception):
    """Custom exception for transaction extraction errors."""
    pass


class ExtractedTransaction:
    """Represents an extracted transaction."""

    def __init__(
        self,
        amount: float,
        transaction_type: str,
        merchant: str,
        transaction_date: datetime,
        currency: str = "INR",
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize extracted transaction.

        Args:
            amount: Transaction amount
            transaction_type: Type (debit/credit)
            merchant: Merchant name
            transaction_date: Transaction date
            currency: Currency code
            category: Transaction category (optional)
            payment_method: Payment method used (optional)
            raw_data: Raw extraction data
        """
        self.amount = amount
        self.transaction_type = transaction_type.lower()
        self.merchant = merchant
        self.transaction_date = transaction_date
        self.currency = currency
        self.category = category
        self.payment_method = payment_method
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "merchant": self.merchant,
            "transaction_date": self.transaction_date.isoformat(),
            "currency": self.currency,
        }
        # Include optional fields if present
        if self.category:
            result["category"] = self.category
        if self.payment_method:
            result["payment_method"] = self.payment_method
        return result

    def is_valid(self) -> bool:
        """
        Check if extraction is valid.

        Returns:
            True if valid, False otherwise
        """
        if self.amount <= 0:
            return False
        if self.transaction_type not in ['debit', 'credit']:
            return False
        if not self.merchant or self.merchant.lower() in ['n/a', 'unknown', '']:
            return False
        return True


class TransactionExtractor:
    """Extracts transaction data from email messages using LLM with versioned prompts."""

    # Deprecated: Use prompt files instead
    EXTRACTION_SYSTEM_PROMPT = """You are an expert financial transaction extractor.
From the provided email content, extract the following transaction details:

- amount (float, the numerical value only, without currency symbols)
- type (string, either "debit" or "credit")
- merchant (string, the name of the vendor or source of funds)
- date (string, in YYYY-MM-DD format. If only day/month is present, assume current year)
- currency (string, e.g., "INR", "USD". Infer from context if not explicitly stated, default to "INR")

If a detail is not clearly present, use "N/A" for strings and 0 for amount.
Return ONLY a valid JSON object with these exact keys: amount, type, merchant, date, currency.

Do not include any explanations, markdown formatting, or additional text. Only return the JSON object."""

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        use_router: bool = False,
        prompt_version: Optional[str] = None,
        use_prompts: bool = True,
        enable_cache: Optional[bool] = None
    ):
        """
        Initialize transaction extractor.

        Args:
            llm_client: Optional LLM client. If not provided, will use factory or router.
            use_router: If True, use LLM router for use-case based selection (default: False).
            prompt_version: Specific prompt version to use (e.g., 'v1', 'v2'). None = latest.
            use_prompts: If True, use PromptManager. If False, use hardcoded prompt (legacy).
            enable_cache: Enable response caching. None = use config setting.

        Note:
            When use_router=True, extraction will use the provider configured for
            the EXTRACTION use case (e.g., Claude for best accuracy).
        """
        # Determine cache setting
        self.enable_cache = enable_cache if enable_cache is not None else settings.cache_enabled

        if llm_client:
            self.llm_client = llm_client
            self.use_router = False
            logger.info("transaction_extractor_initialized", mode="custom_client", cache=self.enable_cache)
        elif use_router:
            from fincli.clients.llm_router import get_llm_router
            self.router = get_llm_router()
            self.llm_client = None  # Will use router instead
            self.use_router = True
            logger.info("transaction_extractor_initialized", mode="router", cache=self.enable_cache)
        else:
            self.llm_client = get_llm_client()
            self.use_router = False
            logger.info("transaction_extractor_initialized", mode="factory", cache=self.enable_cache)

        # Wrap client with cache if enabled
        if self.enable_cache and self.llm_client and not self.use_router:
            self.llm_client = LLMCache(
                llm_client=self.llm_client,
                enable_cache=True,
                ttl_seconds=settings.cache_ttl_seconds,
                max_entries=settings.cache_max_entries
            )
            logger.info("cache_wrapper_enabled")

        # Load prompt template
        self.use_prompts = use_prompts
        self.prompt_version = prompt_version
        if use_prompts:
            try:
                self.prompt_manager = get_prompt_manager()
                self.prompt_template = self.prompt_manager.load_prompt(
                    category='extraction',
                    name='transaction',
                    version=prompt_version
                )
                logger.info(
                    "prompt_loaded",
                    version=self.prompt_template.version,
                    use_prompts=True
                )
            except Exception as e:
                logger.warning(
                    "prompt_load_failed_using_fallback",
                    error=str(e)
                )
                self.use_prompts = False
                self.prompt_template = None
        else:
            self.prompt_template = None
            logger.info("using_legacy_hardcoded_prompt")

    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse date string to datetime object.

        Args:
            date_str: Date string to parse

        Returns:
            Parsed datetime object

        Raises:
            ValueError: If date cannot be parsed
        """
        if date_str.upper() == 'N/A' or not date_str:
            # Default to current date if not available
            return datetime.now()

        try:
            # Try to parse using dateutil
            return date_parser.parse(date_str)
        except Exception as e:
            logger.warning("date_parse_failed", date_str=date_str, error=str(e))
            # Fallback to current date
            return datetime.now()

    def _validate_and_clean(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean extracted data.

        Args:
            data: Raw extracted data

        Returns:
            Cleaned data dictionary

        Raises:
            TransactionExtractorError: If data is invalid
        """
        required_fields = ['amount', 'type', 'merchant', 'date', 'currency']

        # Check required fields
        for field in required_fields:
            if field not in data:
                raise TransactionExtractorError(f"Missing required field: {field}")

        # Clean and validate
        try:
            # Amount
            amount = float(data['amount'])
            if amount < 0:
                raise TransactionExtractorError("Amount cannot be negative")

            # Type
            transaction_type = str(data['type']).strip().lower()
            if transaction_type not in ['debit', 'credit']:
                raise TransactionExtractorError(
                    f"Invalid transaction type: {transaction_type}"
                )

            # Merchant
            merchant = str(data['merchant']).strip()
            if not merchant or merchant.upper() == 'N/A':
                raise TransactionExtractorError("Merchant cannot be N/A or empty")

            # Date
            date_str = str(data['date']).strip()
            transaction_date = self._parse_date(date_str)

            # Currency
            currency = str(data['currency']).strip().upper()
            if currency == 'N/A':
                currency = 'INR'

            # Optional: Category
            category = None
            if 'category' in data and data['category']:
                category = str(data['category']).strip()
                if category.upper() == 'N/A':
                    category = None

            # Optional: Payment Method
            payment_method = None
            if 'payment_method' in data and data['payment_method']:
                payment_method = str(data['payment_method']).strip()
                if payment_method.upper() in ['N/A', 'UNKNOWN']:
                    payment_method = None

            result = {
                'amount': amount,
                'type': transaction_type,
                'merchant': merchant,
                'date': transaction_date,
                'currency': currency
            }

            # Add optional fields if present
            if category:
                result['category'] = category
            if payment_method:
                result['payment_method'] = payment_method

            return result

        except (ValueError, TypeError) as e:
            raise TransactionExtractorError(f"Data validation failed: {e}")

    def extract_from_email(
        self,
        email: EmailMessage
    ) -> Optional[ExtractedTransaction]:
        """
        Extract transaction from email message.

        Args:
            email: EmailMessage object

        Returns:
            ExtractedTransaction or None if extraction fails

        Raises:
            TransactionExtractorError: If extraction fails critically
        """
        logger.info(
            "extracting_transaction_from_email",
            email_id=email.message_id,
            subject=email.subject,
            using_prompts=self.use_prompts,
            prompt_version=self.prompt_template.version if self.prompt_template else "legacy"
        )

        try:
            # Build prompt using template or raw email content
            email_content = email.get_context_text()

            if self.use_prompts and self.prompt_template:
                # Use versioned prompt template
                user_prompt = self.prompt_template.render_user_prompt(
                    email_content=email_content
                )
                system_prompt = self.prompt_template.system_prompt
                max_tokens = self.prompt_template.get_parameter('max_tokens', 500)
            else:
                # Fallback to legacy hardcoded prompt
                user_prompt = email_content
                system_prompt = self.EXTRACTION_SYSTEM_PROMPT
                max_tokens = 500

            # Call LLM to extract
            try:
                if self.use_router:
                    from fincli.clients.llm_router import LLMUseCase
                    raw_data = self.router.extract_json(
                        prompt=user_prompt,
                        use_case=LLMUseCase.EXTRACTION,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens
                    )
                else:
                    raw_data = self.llm_client.extract_json(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens
                    )
            except LLMClientError as e:
                logger.error(
                    "llm_extraction_failed",
                    email_id=email.message_id,
                    error=str(e)
                )
                raise TransactionExtractorError(f"LLM extraction failed: {e}")

            logger.debug(
                "llm_extraction_raw_data",
                email_id=email.message_id,
                raw_data=raw_data
            )

            # Validate and clean
            try:
                cleaned_data = self._validate_and_clean(raw_data)
            except TransactionExtractorError as e:
                logger.warning(
                    "transaction_extraction_validation_failed",
                    email_id=email.message_id,
                    error=str(e)
                )
                # Return None for validation failures (non-critical)
                return None

            # Create ExtractedTransaction
            transaction = ExtractedTransaction(
                amount=cleaned_data['amount'],
                transaction_type=cleaned_data['type'],
                merchant=cleaned_data['merchant'],
                transaction_date=cleaned_data['date'],
                currency=cleaned_data['currency'],
                category=cleaned_data.get('category'),
                payment_method=cleaned_data.get('payment_method'),
                raw_data=raw_data
            )

            # Final validation
            if not transaction.is_valid():
                logger.warning(
                    "extracted_transaction_invalid",
                    email_id=email.message_id,
                    transaction=transaction.to_dict()
                )
                return None

            logger.info(
                "transaction_extracted_successfully",
                email_id=email.message_id,
                merchant=transaction.merchant,
                amount=transaction.amount
            )

            return transaction

        except Exception as e:
            logger.error(
                "unexpected_extraction_error",
                email_id=email.message_id,
                error=str(e)
            )
            raise TransactionExtractorError(f"Unexpected extraction error: {e}")

    def extract_batch(
        self,
        emails: list[EmailMessage]
    ) -> list[tuple[EmailMessage, Optional[ExtractedTransaction]]]:
        """
        Extract transactions from a batch of emails.

        Args:
            emails: List of EmailMessage objects

        Returns:
            List of (email, transaction) tuples
        """
        logger.info("extracting_batch", batch_size=len(emails))

        results = []
        for email in emails:
            try:
                transaction = self.extract_from_email(email)
                results.append((email, transaction))
            except TransactionExtractorError as e:
                logger.error(
                    "batch_extraction_item_failed",
                    email_id=email.message_id,
                    error=str(e)
                )
                # Continue with other emails
                results.append((email, None))

        successful = sum(1 for _, t in results if t is not None)
        logger.info(
            "batch_extraction_completed",
            total=len(emails),
            successful=successful,
            failed=len(emails) - successful
        )

        return results


# Global extractor instance
_extractor: Optional[TransactionExtractor] = None


def get_transaction_extractor() -> TransactionExtractor:
    """
    Get transaction extractor (singleton pattern).

    Returns:
        TransactionExtractor instance
    """
    global _extractor
    if _extractor is None:
        _extractor = TransactionExtractor()
    return _extractor
