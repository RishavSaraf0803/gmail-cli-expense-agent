#!/usr/bin/env python
"""
Seed script to populate the database with dummy transaction data.
This allows you to test the application without connecting to Gmail.

Usage:
    python seed_dummy_data.py [--count 50] [--clear]
"""
import random
import argparse
from datetime import datetime, timedelta
from fincli.storage.database import get_db_manager
from fincli.config import get_settings
from fincli.utils.logger import setup_logging, get_logger

# Setup
settings = get_settings()
setup_logging(log_level=settings.log_level, log_format=settings.log_format)
logger = get_logger(__name__)

# Realistic dummy data
MERCHANTS = [
    # Food & Dining
    ("Starbucks", "Food & Dining", "Credit Card"),
    ("McDonald's", "Food & Dining", "Debit Card"),
    ("Domino's Pizza", "Food & Dining", "UPI"),
    ("Zomato", "Food & Dining", "UPI"),
    ("Swiggy", "Food & Dining", "Credit Card"),
    ("Subway", "Food & Dining", "Cash"),
    ("KFC", "Food & Dining", "Credit Card"),
    ("Pizza Hut", "Food & Dining", "Debit Card"),

    # Shopping
    ("Amazon", "Shopping", "Credit Card"),
    ("Flipkart", "Shopping", "UPI"),
    ("Walmart", "Shopping", "Debit Card"),
    ("Target", "Shopping", "Credit Card"),
    ("Myntra", "Shopping", "Credit Card"),
    ("IKEA", "Shopping", "Debit Card"),

    # Transportation
    ("Uber", "Transportation", "Credit Card"),
    ("Ola Cabs", "Transportation", "UPI"),
    ("Lyft", "Transportation", "Credit Card"),
    ("Indian Railways", "Transportation", "UPI"),
    ("SpiceJet", "Transportation", "Credit Card"),

    # Entertainment
    ("Netflix", "Entertainment", "Credit Card"),
    ("Amazon Prime", "Entertainment", "UPI"),
    ("Spotify", "Entertainment", "Credit Card"),
    ("BookMyShow", "Entertainment", "UPI"),
    ("Disney+ Hotstar", "Entertainment", "Credit Card"),

    # Utilities
    ("Electricity Bill", "Utilities", "Auto Debit"),
    ("Internet Bill", "Utilities", "Auto Debit"),
    ("Phone Bill", "Utilities", "UPI"),
    ("Water Bill", "Utilities", "UPI"),

    # Healthcare
    ("Apollo Pharmacy", "Healthcare", "Credit Card"),
    ("Max Hospital", "Healthcare", "Debit Card"),
    ("HealthCare Clinic", "Healthcare", "Cash"),

    # Fuel
    ("Shell Petrol Pump", "Fuel", "Credit Card"),
    ("HP Gas Station", "Fuel", "UPI"),
    ("Bharat Petroleum", "Fuel", "Credit Card"),

    # Groceries
    ("Big Bazaar", "Groceries", "Debit Card"),
    ("DMart", "Groceries", "Cash"),
    ("Spencer's", "Groceries", "Credit Card"),

    # Income/Credits
    ("Salary Deposit", "Income", "Bank Transfer"),
    ("Freelance Payment", "Income", "Bank Transfer"),
    ("Refund from Amazon", "Refund", "Credit"),
]

# Merchant-specific email subjects and snippets for realistic RAG data.
# Real Gmail emails have rich prose — this is what makes RAG work in production.
MERCHANT_EMAIL_TEMPLATES = {
    "Swiggy": {
        "subjects": ["Swiggy Order Confirmed!", "Your Swiggy order is on its way", "Order delivered - Rate your experience"],
        "snippets": [
            "Your Swiggy food delivery order has been confirmed. Butter Chicken + Garlic Naan + Raita. Estimated delivery: 35 mins.",
            "Great news! Your Swiggy order is out for delivery. The delivery partner is nearby. Track your food order live.",
            "Your Swiggy order has been delivered. Hope you enjoyed your meal! Rate your food delivery experience.",
        ],
    },
    "Zomato": {
        "subjects": ["Zomato: Order Placed Successfully", "Your food is on its way!", "Zomato order delivered"],
        "snippets": [
            "Your Zomato food order has been placed. Dal Makhani, Paneer Butter Masala, 2 Naan. Arriving in 40 minutes.",
            "Your Zomato order is out for delivery. Enjoy your meal! Your delivery partner Rahul is on the way.",
            "Order delivered! Thank you for ordering food on Zomato. Leave a review for the restaurant.",
        ],
    },
    "Domino's Pizza": {
        "subjects": ["Domino's Order Confirmation", "Your pizza is baking!", "Domino's: Order Out for Delivery"],
        "snippets": [
            "Your Domino's Pizza order is confirmed: 1x Margherita Pizza, 1x Garlic Bread, 1x Pepsi. Ready in 30 mins.",
            "Your Domino's pizza is being freshly baked right now. Our delivery partner will reach you soon.",
            "Your Domino's order is out for delivery! Pizza and sides on their way to your door.",
        ],
    },
    "Starbucks": {
        "subjects": ["Starbucks Order Ready", "Your Starbucks order", "Starbucks Stars earned"],
        "snippets": [
            "Your Starbucks coffee order is ready for pickup. Grande Caramel Macchiato + Blueberry Muffin. Stars earned: 15.",
            "Thank you for your Starbucks order. Enjoy your Frappuccino! You have 120 Stars in your account.",
            "Your Starbucks mobile order: Flat White, Chocolate Croissant. Ready at the counter.",
        ],
    },
    "McDonald's": {
        "subjects": ["McDonald's Order Confirmed", "Your McDelivery is on its way"],
        "snippets": [
            "Your McDonald's order: McAloo Tikki Burger, Large Fries, Coke. Estimated delivery 25 minutes.",
            "McDelivery on its way! Big Mac Meal + McFlurry ordered. Track your order in the app.",
        ],
    },
    "KFC": {
        "subjects": ["KFC Order Confirmed", "Your KFC order is ready"],
        "snippets": [
            "Your KFC order: 3pc Chicken Bucket, Coleslaw, Pepsi. Crispy fried chicken is being prepared.",
            "KFC order confirmed: Zinger Burger Meal + Hot Wings. Finger lickin good food on its way.",
        ],
    },
    "Netflix": {
        "subjects": ["Netflix subscription renewed", "Your Netflix payment", "Billing confirmation - Netflix"],
        "snippets": [
            "Your Netflix subscription has been renewed. Plan: Premium HD. Next billing date next month. Enjoy unlimited streaming.",
            "Netflix payment confirmed. You have access to unlimited movies, TV shows, and Netflix Originals. Stream anytime.",
            "Monthly Netflix subscription charge processed. Your account is active. Watch on 4 screens simultaneously.",
        ],
    },
    "Spotify": {
        "subjects": ["Spotify Premium renewed", "Your Spotify subscription"],
        "snippets": [
            "Your Spotify Premium subscription has been renewed. Enjoy ad-free music streaming and offline downloads.",
            "Spotify Premium payment confirmed. Listen to millions of songs and podcasts without interruption.",
        ],
    },
    "Amazon Prime": {
        "subjects": ["Amazon Prime membership renewed", "Your Prime subscription"],
        "snippets": [
            "Your Amazon Prime membership has been renewed. Enjoy free delivery, Prime Video streaming, and exclusive deals.",
            "Amazon Prime subscription active. Benefits: free fast delivery, Prime Video, Prime Music, exclusive offers.",
        ],
    },
    "Disney+ Hotstar": {
        "subjects": ["Hotstar subscription confirmed", "Your Disney+ Hotstar plan"],
        "snippets": [
            "Your Disney+ Hotstar subscription is active. Watch IPL live, Disney movies, Marvel shows and more.",
            "Hotstar Premium renewed. Stream live cricket, Bollywood movies, Hollywood blockbusters and web series.",
        ],
    },
    "BookMyShow": {
        "subjects": ["BookMyShow booking confirmed", "Your movie tickets are booked"],
        "snippets": [
            "Booking confirmed! Movie: Pathaan. 2 tickets, PVR Cinemas, Saturday 7:30 PM. Seats: F12, F13.",
            "Your BookMyShow tickets confirmed. Concert: Arijit Singh Live. 2 seats booked. Venue: MMRDA Grounds.",
        ],
    },
    "Amazon": {
        "subjects": ["Your Amazon order has been placed", "Amazon order shipped", "Amazon delivery confirmation"],
        "snippets": [
            "Your Amazon order has been placed. Products: Wireless Earbuds, Phone Case. Estimated delivery in 2 days.",
            "Your Amazon package has shipped. Tracking available. Product: Laptop Stand, USB Hub. Out for delivery tomorrow.",
            "Amazon order delivered! Your package was left at door. Rate your shopping experience.",
        ],
    },
    "Flipkart": {
        "subjects": ["Flipkart order confirmed", "Your Flipkart order shipped"],
        "snippets": [
            "Your Flipkart order is confirmed: Running Shoes, Sports T-shirt. Wishmaster delivery scheduled.",
            "Flipkart order shipped! Tracking ID provided. Your electronics order is on its way.",
        ],
    },
    "Myntra": {
        "subjects": ["Myntra order placed", "Your fashion order is shipped", "Myntra delivery update"],
        "snippets": [
            "Your Myntra fashion order is confirmed: Casual Shirt (M), Jeans (32). Trendy clothes on their way.",
            "Myntra order shipped! Your ethnic wear and western outfit collection is out for delivery.",
            "Myntra delivery arriving today. Your kurta, dress, and accessories are almost there.",
        ],
    },
    "IKEA": {
        "subjects": ["IKEA order confirmation", "Your IKEA purchase"],
        "snippets": [
            "Your IKEA order confirmed: KALLAX shelf unit, MALM bed frame. Flat-pack furniture delivery scheduled.",
            "IKEA purchase complete. Your home furnishing items including desk and chair are being prepared for delivery.",
        ],
    },
    "Uber": {
        "subjects": ["Your Uber trip receipt", "Uber trip completed", "Thanks for riding with Uber"],
        "snippets": [
            "Thanks for riding with Uber! Trip from Koramangala to Whitefield. Duration: 45 mins. Driver: Suresh (4.9 stars).",
            "Your Uber trip is complete. From Airport to Hotel. Estimated fare charged. Rate your driver.",
            "Uber trip receipt: Indiranagar to MG Road. UberGo. Driver rated 5 stars. Safe ride completed.",
        ],
    },
    "Ola Cabs": {
        "subjects": ["Ola ride receipt", "Thanks for choosing Ola"],
        "snippets": [
            "Your Ola ride completed. From HSR Layout to Electronic City. Ola Mini. Driver: Prakash.",
            "Thanks for choosing Ola! Your ride from home to office is complete. Fare paid via UPI.",
        ],
    },
    "Indian Railways": {
        "subjects": ["IRCTC Booking Confirmation", "Train ticket booked successfully", "e-Ticket PNR confirmed"],
        "snippets": [
            "IRCTC booking confirmed. PNR: 4521893012. Train 12951 Mumbai Rajdhani. Coach B2, Seat 34. Journey date confirmed.",
            "Your train ticket is booked. Rajdhani Express, Sleeper Class, 2 passengers. Platform and boarding details inside.",
            "e-Ticket confirmed via IRCTC. Journey from New Delhi to Mumbai. Tatkal booking successful. Print or show QR code.",
        ],
    },
    "SpiceJet": {
        "subjects": ["SpiceJet flight booking confirmed", "Your flight itinerary", "E-ticket confirmation"],
        "snippets": [
            "Flight booking confirmed! SpiceJet SG-101, Delhi to Mumbai. Departure 06:15 AM. Seat 14A. Check-in online.",
            "Your SpiceJet e-ticket is ready. Bangalore to Hyderabad, economy class. Web check-in opens 24 hours before.",
        ],
    },
    "Shell Petrol Pump": {
        "subjects": ["Shell fuel transaction", "Fuel purchase receipt"],
        "snippets": [
            "Fuel transaction at Shell petrol pump. Petrol filled: 12 litres at current rate. Vehicle: MH-01-AB-1234.",
            "Shell fuel purchase complete. Premium petrol filled. Loyalty points earned on your Shell card.",
        ],
    },
    "HP Gas Station": {
        "subjects": ["HP fuel receipt", "Hindustan Petroleum transaction"],
        "snippets": [
            "HP fuel station transaction. Diesel filled for your vehicle. HP Loyalty program points credited.",
            "Hindustan Petroleum fuel purchase. 15 litres petrol. Transaction at HP outlet.",
        ],
    },
    "Bharat Petroleum": {
        "subjects": ["BPCL fuel transaction", "Bharat Petroleum receipt"],
        "snippets": [
            "Bharat Petroleum fuel purchase at BPCL outlet. Petrol tank filled. SmartDrive loyalty points added.",
            "BPCL transaction complete. CNG/Petrol filled. Bharat Petroleum SmartDrive membership points credited.",
        ],
    },
    "Apollo Pharmacy": {
        "subjects": ["Apollo Pharmacy order confirmed", "Your medicine order", "Apollo health order"],
        "snippets": [
            "Your Apollo Pharmacy order confirmed: Crocin 500mg x10, Vitamin C tablets, BP monitor. Home delivery in 2 hours.",
            "Medicine order placed at Apollo Pharmacy. Prescription medicines and health supplements ordered. Pharmacist verified.",
        ],
    },
    "Max Hospital": {
        "subjects": ["Max Hospital billing receipt", "Your hospital bill", "Max Healthcare payment confirmation"],
        "snippets": [
            "Max Hospital billing receipt. OPD consultation with Dr. Sharma (Cardiology). Includes ECG and blood test charges.",
            "Hospital payment confirmed at Max Hospital. Includes doctor consultation, diagnostic tests, and medicines.",
        ],
    },
    "DMart": {
        "subjects": ["DMart purchase receipt", "Thank you for shopping at DMart"],
        "snippets": [
            "Thank you for shopping at DMart! Grocery items: Rice 5kg, Dal 1kg, Cooking Oil, Vegetables, Snacks. Total bill.",
            "DMart monthly grocery shopping complete. Household essentials, fresh produce, dairy products, and staples purchased.",
        ],
    },
    "Big Bazaar": {
        "subjects": ["Big Bazaar shopping receipt", "Your Big Bazaar purchase"],
        "snippets": [
            "Big Bazaar shopping receipt. Monthly grocery run: atta, rice, pulses, spices, vegetables, toiletries.",
            "Thank you for shopping at Big Bazaar. FMCG products, groceries, and household items. Discount applied.",
        ],
    },
    "Electricity Bill": {
        "subjects": ["Electricity bill payment successful", "BESCOM bill paid", "Power bill payment confirmation"],
        "snippets": [
            "Electricity bill payment successful. BESCOM consumer number: 123456. Units consumed: 245 kWh. Current month bill paid.",
            "Monthly electricity bill paid. Bangalore Electricity Supply Company. Account cleared for this billing cycle.",
        ],
    },
    "Internet Bill": {
        "subjects": ["Broadband bill payment", "Airtel Fiber bill paid", "Internet subscription renewed"],
        "snippets": [
            "Airtel Fiber broadband bill paid. Plan: 300 Mbps unlimited. Account active. No interruption in service.",
            "Internet bill payment successful. Jio Fiber monthly subscription. Unlimited data plan renewed.",
        ],
    },
    "Phone Bill": {
        "subjects": ["Mobile recharge successful", "Postpaid bill payment", "Airtel/Jio bill paid"],
        "snippets": [
            "Mobile postpaid bill paid. Airtel plan: unlimited calls + 40GB data. Bill cleared for current cycle.",
            "Phone bill payment confirmed. Jio postpaid plan. Unlimited 5G data and calling. Account active.",
        ],
    },
    "Salary Deposit": {
        "subjects": ["Salary credited to your account", "Monthly salary deposited"],
        "snippets": [
            "Your monthly salary has been credited to your account. Net salary after deductions. From employer payroll.",
            "Salary deposit confirmed. Monthly CTC credited. PF and tax deducted at source as per records.",
        ],
    },
    "Refund from Amazon": {
        "subjects": ["Amazon refund processed", "Your refund has been initiated"],
        "snippets": [
            "Amazon refund processed for your returned item. Amount will reflect in your account within 3-5 business days.",
            "Refund initiated for your Amazon return. Product: Electronics item returned. Refund to original payment method.",
        ],
    },
}

# Fallback for merchants without specific templates
DEFAULT_SUBJECTS = [
    "Transaction Alert: Your account has been debited",
    "Payment Successful - Transaction Details",
    "UPI Transaction Alert",
    "Debit Alert - Account XX1234",
]

def generate_dummy_transactions(count: int = 50) -> list:
    """
    Generate dummy transaction data.

    Args:
        count: Number of transactions to generate

    Returns:
        List of transaction dictionaries
    """
    transactions = []
    today = datetime.now()

    for i in range(count):
        # Random date in the last 90 days
        days_ago = random.randint(0, 90)
        transaction_date = today - timedelta(days=days_ago)
        email_date = transaction_date + timedelta(minutes=random.randint(1, 30))

        # Pick random merchant
        merchant, category, payment_method = random.choice(MERCHANTS)

        # Determine transaction type based on merchant
        if "Salary" in merchant or "Freelance" in merchant or "Refund" in merchant:
            transaction_type = "credit"
            amount = round(random.uniform(5000, 50000), 2)
        else:
            transaction_type = "debit"
            # Vary amounts by category
            if category in ["Food & Dining", "Groceries"]:
                amount = round(random.uniform(50, 1500), 2)
            elif category in ["Shopping"]:
                amount = round(random.uniform(500, 5000), 2)
            elif category in ["Transportation"]:
                amount = round(random.uniform(100, 2000), 2)
            elif category in ["Entertainment"]:
                amount = round(random.uniform(200, 1000), 2)
            elif category in ["Utilities", "Healthcare"]:
                amount = round(random.uniform(500, 3000), 2)
            elif category == "Fuel":
                amount = round(random.uniform(500, 2500), 2)
            else:
                amount = round(random.uniform(100, 2000), 2)

        # Generate unique email ID
        email_id = f"dummy_{i+1}_{int(transaction_date.timestamp())}"

        # Use merchant-specific templates for rich email text (makes RAG work correctly)
        if merchant in MERCHANT_EMAIL_TEMPLATES:
            templates = MERCHANT_EMAIL_TEMPLATES[merchant]
            subject = random.choice(templates["subjects"])
            snippet = random.choice(templates["snippets"])
        else:
            subject = random.choice(DEFAULT_SUBJECTS)
            snippet = f"Dear Customer, INR {amount} has been {transaction_type}ed from your account at {merchant}"

        # Add some notes occasionally
        notes = None
        if random.random() < 0.3:  # 30% chance of having notes
            notes = random.choice([
                "Personal expense",
                "Business expense",
                "Shared with friends",
                "Gift purchase",
                "Emergency expense",
                None
            ])

        transaction = {
            "email_id": email_id,
            "amount": amount,
            "transaction_type": transaction_type,
            "merchant": merchant,
            "currency": "INR",
            "transaction_date": transaction_date,
            "email_subject": subject,
            "email_snippet": snippet,
            "email_date": email_date,
            "category": category,
            "payment_method": payment_method,
            "notes": notes,
        }

        transactions.append(transaction)

    # Sort by date (most recent first)
    transactions.sort(key=lambda x: x["transaction_date"], reverse=True)

    return transactions


def seed_database(count: int = 50, clear_existing: bool = False):
    """
    Seed the database with dummy transactions.

    Args:
        count: Number of transactions to generate
        clear_existing: If True, clear all existing transactions first
    """
    db = get_db_manager()

    # Initialize database (create tables if they don't exist)
    logger.info("Initializing database...")
    db.create_tables()

    # Clear existing data if requested
    if clear_existing:
        logger.warning("Clearing existing transactions...")
        with db.get_session() as session:
            from fincli.storage.models import Transaction
            session.query(Transaction).delete()
            session.commit()
        logger.info("Existing transactions cleared")

    # Generate dummy transactions
    logger.info(f"Generating {count} dummy transactions...")
    transactions = generate_dummy_transactions(count)

    # Insert into database
    logger.info("Inserting transactions into database...")
    success_count = 0
    error_count = 0

    for txn in transactions:
        try:
            db.add_transaction(**txn)
            success_count += 1
        except Exception as e:
            error_count += 1
            logger.error(f"Failed to insert transaction: {e}")

    logger.info(
        f"Seeding complete: {success_count} transactions inserted, {error_count} errors"
    )

    # Show summary
    print("\n" + "="*60)
    print("✅ Database Seeded Successfully!")
    print("="*60)
    print(f"Total transactions created: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Database location: {settings.database_url}")
    print("\nYou can now use the CLI commands:")
    print("  python cli.py list-transactions")
    print("  python cli.py summarize")
    print("  python cli.py chat")
    print("="*60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed FinCLI database with dummy transaction data"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of transactions to generate (default: 50)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing transactions before seeding"
    )

    args = parser.parse_args()

    # Confirm if clearing existing data
    if args.clear:
        print("\n⚠️  WARNING: This will DELETE all existing transactions!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            print("Cancelled.")
            return

    seed_database(count=args.count, clear_existing=args.clear)


if __name__ == "__main__":
    main()
