-- Migration: Add payment_method column to transactions table
-- Date: 2024-11-29
-- Description: Adds payment_method field to support v3 extraction prompt

-- Add payment_method column (nullable)
ALTER TABLE transactions ADD COLUMN payment_method VARCHAR(50);

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_transactions_payment_method ON transactions(payment_method);

-- Note: category column already exists, no changes needed
