"""
Database migration script for adding payment_method column.

Run this script to update existing databases to support the v3 extraction prompt.
"""
import sqlite3
import sys
from pathlib import Path


def migrate_add_payment_method(db_path: str):
    """Add payment_method column to transactions table."""
    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if payment_method column already exists
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'payment_method' in columns:
            print("✓ payment_method column already exists. No migration needed.")
            return True

        print("Adding payment_method column...")

        # Add payment_method column
        cursor.execute("""
            ALTER TABLE transactions
            ADD COLUMN payment_method VARCHAR(50)
        """)

        # Create index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_payment_method
            ON transactions(payment_method)
        """)

        conn.commit()
        print("✓ Migration completed successfully!")
        print("  - Added payment_method column")
        print("  - Created index on payment_method")

        return True

    except sqlite3.Error as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def main():
    """Main migration function."""
    # Default database path
    default_db = "fincli.db"

    # Allow custom database path from command line
    db_path = sys.argv[1] if len(sys.argv) > 1 else default_db

    if not Path(db_path).exists():
        print(f"✗ Database not found: {db_path}")
        print(f"  If this is a new installation, the database will be created automatically.")
        print(f"  No migration needed.")
        sys.exit(0)

    print(f"=== FinCLI Database Migration ===")
    print(f"Database: {db_path}")
    print(f"Migration: Add payment_method column")
    print()

    success = migrate_add_payment_method(db_path)

    if success:
        print()
        print("Migration complete! You can now use the v3 extraction prompt.")
        sys.exit(0)
    else:
        print()
        print("Migration failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
