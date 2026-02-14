#!/usr/bin/env python3
"""
Jersey Management Telegram Bot
Main application file with admin design management
"""

import logging
from datetime import datetime
from functools import wraps
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

from config import (
    BOT_TOKEN, ADMIN_IDS, SHIRT_SIZES,
    DATE_FORMAT, WELCOME_MESSAGE, VOTE_DEADLINE_PASSED,
    ORDER_DEADLINE_PASSED, DUPLICATE_VOTE, DUPLICATE_ORDER,
    ORDER_SUCCESS
)
from database import Database
from models import Order

#!/usr/bin/env python3
"""
Jersey Management Telegram Bot
Main application file with ConversationHandler for order flow
"""

import logging
from datetime import datetime
from functools import wraps
from typing import Dict, Any
import threading
import os
import time

# 🌟 FIX FOR RENDER: Simple HTTP server for health checks
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Jersey Bot is running!')
    
    def log_message(self, format, *args):
        # Suppress log messages
        pass

def run_health_server():
    """Run a simple HTTP server on the required port"""
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Health check server running on port {port}")
    server.serve_forever()

# Start health server in background thread
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()
print("✅ Health check server started")

# Give it a moment to start
time.sleep(1)

# Your existing imports...
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# Rest of your code continues exactly as before...

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db = Database()

# Conversation states
(
    NAME, 
    SHIRT_NUMBER, 
    SHIRT_NAME, 
    SIZE, 
    RECEIPT,
    # Admin design management states
    DESIGN_NAME,
    DESIGN_DESC,
    DESIGN_IMAGE,
    DESIGN_EDIT_NAME,
    DESIGN_EDIT_DESC,
    DESIGN_EDIT_IMAGE,
    DESIGN_CONFIRM  # Added this missing state
) = range(12)  # Changed from 11 to 12

# Temporary storage for user data
user_data_cache: Dict[int, Dict[str, Any]] = {}

def admin_only(func):
    """Decorator to restrict commands to admins only"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⛔ This command is for admins only.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    deadlines = db.get_deadlines()
    
    # Register user in database
    db.create_user(update.effective_user.id)
    
    await update.message.reply_text(
        WELCOME_MESSAGE.format(
            vote_deadline=deadlines.vote_deadline.strftime(DATE_FORMAT),
            payment_deadline=deadlines.payment_deadline.strftime(DATE_FORMAT)
        )
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    deadlines = db.get_deadlines()
    
    help_text = """
📚 **Jersey Bot Commands**

**For Everyone:**
/start - Welcome message & deadlines
/vote - Vote for jersey designs
/order - Place your jersey order
/help - Show this message

**For Admins Only:**
📝 **Design Management:**
/add_design - Add new jersey design
/list_designs - View all designs
/edit_design - Edit existing design
/delete_design - Remove a design

⏰ **Deadline Management:**
/set_vote_deadline YYYY-MM-DD HH:MM
/set_payment_deadline YYYY-MM-DD HH:MM
/deadlines - View current deadlines

📊 **Monitoring:**
/results - View voting results
/orders - View order statistics
/export - Export orders to CSV
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ==================== VOTING SYSTEM WITH DYNAMIC DESIGNS ====================

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vote command - Shows all active designs"""
    user_id = update.effective_user.id
    deadlines = db.get_deadlines()
    
    # Check vote deadline
    if datetime.now() > deadlines.vote_deadline:
        await update.message.reply_text(
            VOTE_DEADLINE_PASSED.format(deadline=deadlines.vote_deadline.strftime(DATE_FORMAT))
        )
        return
    
    # Check if user already voted
    if db.has_user_voted(user_id):
        await update.message.reply_text(DUPLICATE_VOTE)
        return
    
    # Get active designs from database
    designs = db.get_active_designs()
    
    if not designs:
        await update.message.reply_text(
            "❌ No designs available for voting yet. Please check back later."
        )
        return
    
    # Send each design with its image and vote button
    for design in designs:
        # Create button for this specific design
        keyboard = [[InlineKeyboardButton(
            f"🗳️ Vote for {design.name}", 
            callback_data=f"vote_{design.id}"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Create caption
        caption = f"📸 **{design.name}**\n\n"
        if design.description:
            caption += f"_{design.description}_\n\n"
        caption += "Click the button below to vote for this design."
        
        # Send image with caption
        try:
            await update.message.reply_photo(
                photo=design.image_file_id,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            logger.info(f"Sent design {design.id} to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send image for design {design.id}: {e}")
            await update.message.reply_text(
                f"❌ Failed to load image for {design.name}. Please try again later."
            )
    
    await update.message.reply_text(
        "🗳️ **Please select your preferred design from the images above.**", 
        parse_mode='Markdown'
    )

async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle vote button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    design_id = int(query.data.replace('vote_', ''))
    
    # Double-check deadline
    deadlines = db.get_deadlines()
    if datetime.now() > deadlines.vote_deadline:
        await query.edit_message_caption(
            caption=VOTE_DEADLINE_PASSED.format(deadline=deadlines.vote_deadline.strftime(DATE_FORMAT))
        )
        return
    
    # Check if user already voted (double-check)
    if db.has_user_voted(user_id):
        await query.edit_message_caption(
            caption=DUPLICATE_VOTE
        )
        return
    
    # Get design details
    design = db.get_design(design_id)
    if not design:
        await query.edit_message_caption(
            caption="❌ This design is no longer available."
        )
        return
    
    # Save vote
    db.save_vote(user_id, design_id)
    
    # Update the message to show vote confirmation
    await query.edit_message_caption(
        caption=f"✅ **Vote Recorded!**\n\nYou voted for: **{design.name}**\n\nThank you for participating! 🎉",
        parse_mode='Markdown'
    )
    
    # Also send a confirmation message
    await query.message.reply_text(
        f"✅ Your vote for **{design.name}** has been saved!",
        parse_mode='Markdown'
    )

# ==================== ADMIN DESIGN MANAGEMENT ====================

@admin_only
async def add_design_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add design conversation"""
    user_id = update.effective_user.id
    
    # Initialize user data
    user_data_cache[user_id] = {'action': 'add_design'}
    
    await update.message.reply_text(
        "📝 **Add New Jersey Design**\n\n"
        "Please enter the **name** of the design (e.g., 'Classic Stripes'):",
        parse_mode='Markdown'
    )
    return DESIGN_NAME

async def add_design_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get design name"""
    user_id = update.effective_user.id
    name = update.message.text.strip()
    
    if not name or len(name) > 100:
        await update.message.reply_text(
            "❌ Please enter a valid name (1-100 characters):"
        )
        return DESIGN_NAME
    
    user_data_cache[user_id]['design_name'] = name
    
    await update.message.reply_text(
        "📝 Now enter a **description** for the design (or send /skip to skip):",
        parse_mode='Markdown'
    )
    return DESIGN_DESC

async def add_design_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get design description"""
    user_id = update.effective_user.id
    description = update.message.text.strip()
    
    user_data_cache[user_id]['design_description'] = description
    
    await update.message.reply_text(
        "📸 Now **upload the design image**.\n\n"
        "Send me a clear photo of the jersey design:"
    )
    return DESIGN_IMAGE

async def add_design_skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip description"""
    user_id = update.effective_user.id
    user_data_cache[user_id]['design_description'] = ""
    
    await update.message.reply_text(
        "📸 Now **upload the design image**.\n\n"
        "Send me a clear photo of the jersey design:"
    )
    return DESIGN_IMAGE

async def add_design_get_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get design image"""
    user_id = update.effective_user.id
    
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please upload a photo of the design:"
        )
        return DESIGN_IMAGE
    
    # Get the largest photo (best quality)
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    design_data = user_data_cache.get(user_id)
    if not design_data:
        await update.message.reply_text("❌ Session expired. Please start over with /add_design")
        return ConversationHandler.END
    
    # Save to database
    design_id = db.add_design(
        name=design_data['design_name'],
        description=design_data['design_description'],
        image_file_id=file_id
    )
    
    # Clear cached data
    del user_data_cache[user_id]
    
    # Send confirmation with the uploaded image
    await update.message.reply_photo(
        photo=file_id,
        caption=f"✅ **Design Added Successfully!**\n\n"
                f"**ID:** {design_id}\n"
                f"**Name:** {design_data['design_name']}\n"
                f"**Description:** {design_data['design_description'] or 'None'}\n\n"
                f"Users can now vote for this design.",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

@admin_only
async def list_designs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all designs"""
    designs = db.get_active_designs()
    
    if not designs:
        await update.message.reply_text("📭 No designs found. Use /add_design to add one.")
        return
    
    message = "📋 **Current Jersey Designs:**\n\n"
    
    for i, design in enumerate(designs, 1):
        message += f"{i}. **{design.name}**\n"
        if design.description:
            message += f"   📝 {design.description[:50]}{'...' if len(design.description) > 50 else ''}\n"
        message += f"   🆔 ID: `{design.id}`\n\n"
    
    message += "\nUse /edit_design to modify or /delete_design to remove."
    
    await update.message.reply_text(message, parse_mode='Markdown')

@admin_only
async def delete_design(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a design"""
    try:
        if not context.args:
            await update.message.reply_text(
                "Usage: /delete_design <design_id>\n"
                "Example: /delete_design 3"
            )
            return
        
        design_id = int(context.args[0])
        design = db.get_design(design_id)
        
        if not design:
            await update.message.reply_text(f"❌ Design with ID {design_id} not found.")
            return
        
        # Soft delete
        db.delete_design(design_id)
        
        await update.message.reply_text(
            f"✅ Design **{design.name}** has been deleted.\n"
            f"It will no longer appear in voting.",
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Invalid design ID. Please provide a number.")
    except Exception as e:
        logger.error(f"Delete design error: {e}")
        await update.message.reply_text("❌ Failed to delete design.")

# ==================== ORDER CONVERSATION HANDLERS ====================

async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the order conversation"""
    user_id = update.effective_user.id
    deadlines = db.get_deadlines()
    
    # Check payment deadline
    if datetime.now() > deadlines.payment_deadline:
        await update.message.reply_text(
            ORDER_DEADLINE_PASSED.format(deadline=deadlines.payment_deadline.strftime(DATE_FORMAT))
        )
        return ConversationHandler.END
    
    # Check if user already ordered
    if db.has_user_ordered(user_id):
        await update.message.reply_text(DUPLICATE_ORDER)
        return ConversationHandler.END
    
    # Initialize user data
    user_data_cache[user_id] = {'telegram_id': user_id}
    
    await update.message.reply_text(
        "📝 Let's start your jersey order!\n\n"
        "Please enter your full name:"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's full name"""
    user_id = update.effective_user.id
    name = update.message.text.strip()
    
    if not name:
        await update.message.reply_text("❌ Name cannot be empty. Please enter your full name:")
        return NAME
    
    user_data_cache[user_id]['full_name'] = name
    
    await update.message.reply_text(
        "🔢 Please enter your desired shirt number (e.g., 10, 23, 99):"
    )
    return SHIRT_NUMBER

async def get_shirt_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get shirt number"""
    user_id = update.effective_user.id
    number_text = update.message.text.strip()
    
    if not number_text.isdigit():
        await update.message.reply_text("❌ Please enter a valid number (digits only):")
        return SHIRT_NUMBER
    
    number = int(number_text)
    if number < 0 or number > 999:
        await update.message.reply_text("❌ Please enter a number between 0 and 999:")
        return SHIRT_NUMBER
    
    user_data_cache[user_id]['shirt_number'] = number
    
    await update.message.reply_text(
        "📝 Please enter the name to print on the shirt (e.g., 'JOHN', 'COACH'):"
    )
    return SHIRT_NAME

async def get_shirt_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get shirt name"""
    user_id = update.effective_user.id
    shirt_name = update.message.text.strip().upper()
    
    if not shirt_name or len(shirt_name) > 15:
        await update.message.reply_text(
            "❌ Please enter a valid name (1-15 characters):"
        )
        return SHIRT_NAME
    
    user_data_cache[user_id]['shirt_name'] = shirt_name
    
    # Create size selection keyboard
    keyboard = [
        [InlineKeyboardButton(size, callback_data=f"size_{size}")]
        for size in SHIRT_SIZES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📏 Please select your shirt size:",
        reply_markup=reply_markup
    )
    return SIZE

async def size_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle size selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    size = query.data.replace('size_', '')
    
    user_data_cache[user_id]['size'] = size
    
    await query.edit_message_text(
        "💳 Please upload your payment receipt as a photo.\n"
        "Make sure the photo is clear and shows the payment details."
    )
    return RECEIPT

async def get_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get payment receipt photo"""
    user_id = update.effective_user.id
    
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please upload a photo of your payment receipt:"
        )
        return RECEIPT
    
    # Get the largest photo (best quality)
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # Save order to database
    order_data = user_data_cache.get(user_id)
    if not order_data:
        await update.message.reply_text("❌ Session expired. Please start over with /order")
        return ConversationHandler.END
    
    order = Order(
        telegram_id=user_id,
        full_name=order_data['full_name'],
        shirt_number=order_data['shirt_number'],
        shirt_name=order_data['shirt_name'],
        size=order_data['size'],
        receipt_file_id=file_id,
        payment_time=datetime.now()
    )
    
    db.save_order(order)
    
    # Clear cached data
    del user_data_cache[user_id]
    
    # Send confirmation
    await update.message.reply_text(
        ORDER_SUCCESS.format(
            name=order.full_name,
            number=order.shirt_number,
            shirt_name=order.shirt_name,
            size=order.size
        )
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any conversation"""
    user_id = update.effective_user.id
    if user_id in user_data_cache:
        del user_data_cache[user_id]
    
    await update.message.reply_text(
        "❌ Operation cancelled. You can start over with the appropriate command."
    )
    return ConversationHandler.END

# ==================== EXISTING ADMIN COMMANDS ====================

@admin_only
async def set_vote_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set new vote deadline"""
    try:
        if not context.args:
            await update.message.reply_text(
                f"Usage: /set_vote_deadline {DATE_FORMAT}\n"
                f"Example: /set_vote_deadline 2024-12-31 23:59"
            )
            return
        
        deadline_str = ' '.join(context.args)
        deadline = datetime.strptime(deadline_str, DATE_FORMAT)
        
        db.set_vote_deadline(deadline)
        
        await update.message.reply_text(
            f"✅ Vote deadline updated to: {deadline.strftime(DATE_FORMAT)}"
        )
    except ValueError:
        await update.message.reply_text(
            f"❌ Invalid date format. Please use: {DATE_FORMAT}\n"
            f"Example: /set_vote_deadline 2024-12-31 23:59"
        )

@admin_only
async def set_payment_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set new payment deadline"""
    try:
        if not context.args:
            await update.message.reply_text(
                f"Usage: /set_payment_deadline {DATE_FORMAT}\n"
                f"Example: /set_payment_deadline 2024-12-31 23:59"
            )
            return
        
        deadline_str = ' '.join(context.args)
        deadline = datetime.strptime(deadline_str, DATE_FORMAT)
        
        db.set_payment_deadline(deadline)
        
        await update.message.reply_text(
            f"✅ Payment deadline updated to: {deadline.strftime(DATE_FORMAT)}"
        )
    except ValueError:
        await update.message.reply_text(
            f"❌ Invalid date format. Please use: {DATE_FORMAT}\n"
            f"Example: /set_payment_deadline 2024-12-31 23:59"
        )

@admin_only
async def show_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current deadlines"""
    deadlines = db.get_deadlines()
    
    await update.message.reply_text(
        f"📅 Current Deadlines:\n\n"
        f"🗳️ Vote Deadline: {deadlines.vote_deadline.strftime(DATE_FORMAT)}\n"
        f"💳 Payment Deadline: {deadlines.payment_deadline.strftime(DATE_FORMAT)}"
    )

@admin_only
async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show voting results"""
    results = db.get_vote_results()
    
    if not results:
        await update.message.reply_text("No votes have been cast yet.")
        return
    
    message = "📊 **Voting Results:**\n\n"
    total_votes = 0
    
    for design_name, count in results:
        message += f"• {design_name}: **{count}** votes\n"
        total_votes += count
    
    message += f"\n**Total Votes: {total_votes}**"
    
    await update.message.reply_text(message, parse_mode='Markdown')

@admin_only
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show order statistics"""
    total = db.get_total_orders()
    await update.message.reply_text(f"📦 **Total Orders:** {total}", parse_mode='Markdown')

@admin_only
async def export_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export orders to CSV"""
    try:
        csv_data = db.export_orders_to_csv()
        
        # Send as file
        await update.message.reply_document(
            document=csv_data.encode('utf-8'),
            filename=f'orders_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            caption="📊 Orders export completed!"
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        await update.message.reply_text("❌ Failed to export orders. Please try again.")

# ==================== MAIN FUNCTION ====================

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Create conversation handler for orders
    order_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('order', order_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            SHIRT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_shirt_number)],
            SHIRT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_shirt_name)],
            SIZE: [CallbackQueryHandler(size_callback, pattern='^size_')],
            RECEIPT: [MessageHandler(filters.PHOTO, get_receipt)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name="order_conversation",
        persistent=False
    )
    
    # Create conversation handler for adding designs
    add_design_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_design', add_design_start)],
        states={
            DESIGN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_design_get_name)],
            DESIGN_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_design_get_desc),
                CommandHandler('skip', add_design_skip_desc)
            ],
            DESIGN_IMAGE: [MessageHandler(filters.PHOTO, add_design_get_image)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name="add_design_conversation",
        persistent=False
    )
    
    # Register handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('vote', vote))
    application.add_handler(CallbackQueryHandler(vote_callback, pattern='^vote_'))
    application.add_handler(order_conv_handler)
    application.add_handler(add_design_conv_handler)
    
    # Admin commands
    application.add_handler(CommandHandler('list_designs', list_designs))
    application.add_handler(CommandHandler('delete_design', delete_design))
    application.add_handler(CommandHandler('set_vote_deadline', set_vote_deadline))
    application.add_handler(CommandHandler('set_payment_deadline', set_payment_deadline))
    application.add_handler(CommandHandler('deadlines', show_deadlines))
    application.add_handler(CommandHandler('results', show_results))
    application.add_handler(CommandHandler('orders', show_orders))
    application.add_handler(CommandHandler('export', export_orders))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Starting Jersey Management Bot with Dynamic Design Management...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again or contact admin."
        )

if __name__ == '__main__':
    main()