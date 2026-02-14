import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found in environment variables")

# Admin Configuration (Hardcoded Admin IDs)
ADMIN_IDS = [667804575]  # Replace with your Telegram ID

# Database Configuration
DATABASE_NAME = 'deadlines.db'

# Shirt Sizes
SHIRT_SIZES = ['S', 'M', 'L', 'XL', 'XXL']

# Date Format
DATE_FORMAT = '%Y-%m-%d %H:%M'

# Messages
WELCOME_MESSAGE = """
👕 Welcome to Jersey Management Bot!

Current Deadlines:
🗳️ Voting Deadline: {vote_deadline}
💳 Payment Deadline: {payment_deadline}

⚠️ No late submissions are accepted after deadlines!

Available Commands:
/vote - Vote for jersey design
/order - Place jersey order
/help - Show all commands
"""

VOTE_DEADLINE_PASSED = """
❌ Voting deadline has passed!
Deadline was: {deadline}
No late votes are accepted.
"""

ORDER_DEADLINE_PASSED = """
❌ Payment deadline has passed!
Deadline was: {deadline}
No late orders are accepted.
"""

DUPLICATE_VOTE = "❌ You have already voted! Each user can only vote once."

DUPLICATE_ORDER = "❌ You have already placed an order! Each user can only order once."

ORDER_SUCCESS = """
✅ Order placed successfully!

Order Summary:
👤 Name: {name}
🔢 Number: {number}
📝 Shirt Name: {shirt_name}
📏 Size: {size}
💳 Payment Receipt: Received

Thank you for your order!
"""