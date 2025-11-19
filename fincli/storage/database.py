"""
Database operations and session management for FinCLI.
"""
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Generator
from sqlalchemy import create_engine, select, func, and_
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from fincli.storage.models import Base, Transaction
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_url: Database connection URL. If None, uses config.
        """
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(
            self.database_url,
            echo=settings.database_echo,
            pool_pre_ping=True,  # Verify connections before using
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        logger.info("database_initialized", url=self.database_url)

    def create_tables(self) -> None:
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("database_tables_created")
        except SQLAlchemyError as e:
            logger.error("database_table_creation_failed", error=str(e))
            raise

    def drop_tables(self) -> None:
        """Drop all database tables (use with caution!)."""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("database_tables_dropped")
        except SQLAlchemyError as e:
            logger.error("database_table_drop_failed", error=str(e))
            raise

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session context manager.

        Yields:
            SQLAlchemy session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _expunge_all(self, session: Session, items: List) -> None:
        """
        Expunge all items from session.

        Args:
            session: SQLAlchemy session
            items: List of ORM objects to expunge
        """
        for item in items:
            if item:
                session.expunge(item)

    def add_transaction(
        self,
        email_id: str,
        amount: float,
        transaction_type: str,
        merchant: str,
        transaction_date: datetime,
        currency: str = "INR",
        email_subject: Optional[str] = None,
        email_snippet: Optional[str] = None,
        email_date: Optional[datetime] = None,
        category: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Transaction]:
        """
        Add a new transaction to the database.

        Args:
            email_id: Gmail message ID
            amount: Transaction amount
            transaction_type: Type (debit/credit)
            merchant: Merchant name
            transaction_date: Date of transaction
            currency: Currency code
            email_subject: Email subject
            email_snippet: Email snippet
            email_date: Email date
            category: Transaction category
            notes: Additional notes

        Returns:
            Created Transaction object or None if duplicate
        """
        try:
            with self.get_session() as session:
                transaction = Transaction(
                    email_id=email_id,
                    amount=amount,
                    transaction_type=transaction_type.lower(),
                    merchant=merchant,
                    currency=currency,
                    transaction_date=transaction_date,
                    email_subject=email_subject,
                    email_snippet=email_snippet,
                    email_date=email_date,
                    category=category,
                    notes=notes,
                )
                session.add(transaction)
                session.commit()
                session.refresh(transaction)
                # Expunge to detach from session before returning
                session.expunge(transaction)
                logger.info(
                    "transaction_added",
                    email_id=email_id,
                    merchant=merchant,
                    amount=amount
                )
                return transaction
        except IntegrityError:
            logger.debug(
                "transaction_duplicate_skipped",
                email_id=email_id
            )
            return None
        except SQLAlchemyError as e:
            logger.error("transaction_add_failed", error=str(e), email_id=email_id)
            raise

    def get_transaction_by_email_id(self, email_id: str) -> Optional[Transaction]:
        """
        Get a transaction by email ID.

        Args:
            email_id: Gmail message ID

        Returns:
            Transaction object or None
        """
        try:
            with self.get_session() as session:
                stmt = select(Transaction).where(Transaction.email_id == email_id)
                transaction = session.execute(stmt).scalar_one_or_none()
                if transaction:
                    # Expunge to detach from session before returning
                    session.expunge(transaction)
                return transaction
        except SQLAlchemyError as e:
            logger.error("transaction_fetch_failed", error=str(e), email_id=email_id)
            raise

    def get_all_transactions(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Get all transactions with optional pagination.

        Args:
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip

        Returns:
            List of Transaction objects
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(Transaction)
                    .order_by(Transaction.transaction_date.desc())
                    .offset(offset)
                )
                if limit:
                    stmt = stmt.limit(limit)
                transactions = list(session.execute(stmt).scalars().all())
                # Expunge all to detach from session
                self._expunge_all(session, transactions)
                return transactions
        except SQLAlchemyError as e:
            logger.error("transactions_fetch_failed", error=str(e))
            raise

    def get_transactions_by_type(
        self,
        transaction_type: str,
        limit: Optional[int] = None
    ) -> List[Transaction]:
        """
        Get transactions by type (debit/credit).

        Args:
            transaction_type: Type to filter by
            limit: Maximum number of transactions to return

        Returns:
            List of Transaction objects
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(Transaction)
                    .where(Transaction.transaction_type == transaction_type.lower())
                    .order_by(Transaction.transaction_date.desc())
                )
                if limit:
                    stmt = stmt.limit(limit)
                transactions = list(session.execute(stmt).scalars().all())
                # Expunge all to detach from session
                self._expunge_all(session, transactions)
                return transactions
        except SQLAlchemyError as e:
            logger.error("transactions_by_type_fetch_failed", error=str(e))
            raise

    def get_transactions_by_merchant(
        self,
        merchant: str,
        limit: Optional[int] = None
    ) -> List[Transaction]:
        """
        Get transactions by merchant.

        Args:
            merchant: Merchant name to filter by
            limit: Maximum number of transactions to return

        Returns:
            List of Transaction objects
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(Transaction)
                    .where(Transaction.merchant.ilike(f"%{merchant}%"))
                    .order_by(Transaction.transaction_date.desc())
                )
                if limit:
                    stmt = stmt.limit(limit)
                transactions = list(session.execute(stmt).scalars().all())
                # Expunge all to detach from session
                self._expunge_all(session, transactions)
                return transactions
        except SQLAlchemyError as e:
            logger.error("transactions_by_merchant_fetch_failed", error=str(e))
            raise

    def get_transactions_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None
    ) -> List[Transaction]:
        """
        Get transactions within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Maximum number of transactions to return

        Returns:
            List of Transaction objects
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(Transaction)
                    .where(and_(
                        Transaction.transaction_date >= start_date,
                        Transaction.transaction_date <= end_date
                    ))
                    .order_by(Transaction.transaction_date.desc())
                )
                if limit:
                    stmt = stmt.limit(limit)
                transactions = list(session.execute(stmt).scalars().all())
                # Expunge all to detach from session
                self._expunge_all(session, transactions)
                return transactions
        except SQLAlchemyError as e:
            logger.error("transactions_by_date_range_fetch_failed", error=str(e))
            raise

    def get_total_by_type(self, transaction_type: str) -> float:
        """
        Get total amount for a transaction type.

        Args:
            transaction_type: Type to sum (debit/credit)

        Returns:
            Total amount
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(func.sum(Transaction.amount))
                    .where(Transaction.transaction_type == transaction_type.lower())
                )
                result = session.execute(stmt).scalar()
                return float(result) if result else 0.0
        except SQLAlchemyError as e:
            logger.error("total_by_type_calculation_failed", error=str(e))
            raise

    def get_top_merchants(
        self,
        transaction_type: Optional[str] = None,
        limit: int = 10
    ) -> List[tuple]:
        """
        Get top merchants by transaction count.

        Args:
            transaction_type: Filter by type (optional)
            limit: Number of top merchants to return

        Returns:
            List of (merchant, count) tuples
        """
        try:
            with self.get_session() as session:
                stmt = (
                    select(
                        Transaction.merchant,
                        func.count(Transaction.id).label('count')
                    )
                    .group_by(Transaction.merchant)
                    .order_by(func.count(Transaction.id).desc())
                    .limit(limit)
                )
                if transaction_type:
                    stmt = stmt.where(
                        Transaction.transaction_type == transaction_type.lower()
                    )
                return list(session.execute(stmt).all())
        except SQLAlchemyError as e:
            logger.error("top_merchants_fetch_failed", error=str(e))
            raise

    def count_transactions(self) -> int:
        """
        Get total count of transactions.

        Returns:
            Transaction count
        """
        try:
            with self.get_session() as session:
                stmt = select(func.count(Transaction.id))
                return session.execute(stmt).scalar() or 0
        except SQLAlchemyError as e:
            logger.error("transaction_count_failed", error=str(e))
            raise


# Global database manager instance
db_manager = DatabaseManager()


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    return db_manager


def init_database() -> None:
    """Initialize the database (create tables)."""
    db_manager.create_tables()
