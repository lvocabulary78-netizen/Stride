import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states for admin
WORD, MEANING, EXAMPLE = range(3)

# File to store dictionary
DICTIONARY_FILE = 'dictionary.json'

# Admin user IDs (you'll add your Telegram user ID here)
ADMIN_IDS = []  # Add your Telegram user ID here, e.g., [123456789, 987654321]


# Simple HTTP handler for Render health checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def run_health_server():
    """Run a simple HTTP server for health checks"""
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f'Health check server running on port {port}')
    server.serve_forever()


def load_dictionary():
    """Load dictionary from JSON file"""
    if os.path.exists(DICTIONARY_FILE):
        with open(DICTIONARY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_dictionary(dictionary):
    """Save dictionary to JSON file"""
    with open(DICTIONARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, indent=2, ensure_ascii=False)


def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    user = update.effective_user
    welcome_text = f"👋 Welcome *{user.first_name}*!\n\n"
    
    if is_admin(user.id):
        welcome_text += (
            "🎓 *Dictionary Bot - Admin Mode*\n\n"
            "📚 *For Students:*\n"
            "• Just type any word to get its meaning and examples\n"
            "• Type multiple words separated by commas for batch lookup\n\n"
            "⚙️ *Admin Commands:*\n"
            "• /add - Add a new word to dictionary\n"
            "• /delete - Remove a word from dictionary\n"
            "• /list - View all words in dictionary\n"
            "• /stats - Get dictionary statistics\n"
            "• /backup - Download dictionary backup\n\n"
            "Let's build an amazing dictionary! 🚀"
        )
    else:
        welcome_text += (
            "🎓 *Dictionary Bot - Student Mode*\n\n"
            "📚 *How to use:*\n"
            "• Type any word to get its meaning and examples\n"
            "• Type multiple words separated by commas\n"
            "  Example: `happy, sad, excited`\n\n"
            "💡 *Tips:*\n"
            "• Searches are case-insensitive\n"
            "• Works with partial word matches\n\n"
            "Start learning now! 📖✨"
        )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def add_word_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the process of adding a word (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ This command is only available to admins.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 *Add New Word*\n\n"
        "Please enter the word you want to add:\n\n"
        "Type /cancel to abort.",
        parse_mode='Markdown'
    )
    return WORD


async def receive_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the word from admin"""
    word = update.message.text.strip().lower()
    context.user_data['new_word'] = word
    
    dictionary = load_dictionary()
    if word in dictionary:
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Update", callback_data=f"update_{word}"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="cancel_add")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"⚠️ The word *'{word}'* already exists!\n\n"
            f"Current meaning: {dictionary[word]['meaning']}\n\n"
            f"Do you want to update it?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return WORD
    
    await update.message.reply_text(
        f"✏️ Word: *{word}*\n\n"
        f"Now, please enter the *meaning* of this word:",
        parse_mode='Markdown'
    )
    return MEANING


async def receive_meaning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the meaning from admin"""
    meaning = update.message.text.strip()
    context.user_data['meaning'] = meaning
    
    await update.message.reply_text(
        "📋 Great! Now please enter *example sentences*.\n\n"
        "You can enter multiple examples, one per line.\n"
        "Press Enter after each example:\n\n"
        "Example:\n"
        "`She was happy to see her friends.`\n"
        "`I feel happy when I help others.`",
        parse_mode='Markdown'
    )
    return EXAMPLE


async def receive_examples(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive examples and save the word"""
    examples_text = update.message.text.strip()
    examples = [ex.strip() for ex in examples_text.split('\n') if ex.strip()]
    
    word = context.user_data['new_word']
    meaning = context.user_data['meaning']
    
    dictionary = load_dictionary()
    dictionary[word] = {
        'meaning': meaning,
        'examples': examples
    }
    save_dictionary(dictionary)
    
    # Clear user data
    context.user_data.clear()
    
    # Create beautiful confirmation message
    examples_formatted = '\n'.join([f"  • {ex}" for ex in examples])
    
    await update.message.reply_text(
        f"✅ *Word Added Successfully!*\n\n"
        f"📖 *Word:* {word}\n"
        f"💡 *Meaning:* {meaning}\n"
        f"📝 *Examples:*\n{examples_formatted}\n\n"
        f"The word is now available to all students! 🎉",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the add word process"""
    context.user_data.clear()
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "❌ Operation cancelled. No changes were made."
        )
    else:
        await update.message.reply_text(
            "❌ Operation cancelled. No changes were made."
        )
    
    return ConversationHandler.END


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("update_"):
        word = query.data.replace("update_", "")
        context.user_data['new_word'] = word
        await query.message.reply_text(
            f"✏️ Updating word: *{word}*\n\n"
            f"Please enter the new *meaning*:",
            parse_mode='Markdown'
        )
        return MEANING
    elif query.data == "cancel_add":
        return await cancel_add(update, context)


async def delete_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a word from dictionary (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Please specify a word to delete.\n\n"
            "Usage: `/delete word`",
            parse_mode='Markdown'
        )
        return
    
    word = ' '.join(context.args).lower()
    dictionary = load_dictionary()
    
    if word in dictionary:
        del dictionary[word]
        save_dictionary(dictionary)
        await update.message.reply_text(
            f"✅ Word *'{word}'* has been deleted from the dictionary.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ Word *'{word}'* not found in dictionary.",
            parse_mode='Markdown'
        )


async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all words in dictionary (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ This command is only available to admins.")
        return
    
    dictionary = load_dictionary()
    
    if not dictionary:
        await update.message.reply_text("📚 Dictionary is empty. Add some words to get started!")
        return
    
    words = sorted(dictionary.keys())
    words_list = '\n'.join([f"• {word}" for word in words])
    
    message = f"📚 *Dictionary Words ({len(words)} total)*\n\n{words_list}"
    
    # Split message if too long
    if len(message) > 4000:
        chunks = [words[i:i+50] for i in range(0, len(words), 50)]
        for i, chunk in enumerate(chunks):
            chunk_text = '\n'.join([f"• {word}" for word in chunk])
            await update.message.reply_text(
                f"📚 *Dictionary Words (Part {i+1}/{len(chunks)})*\n\n{chunk_text}",
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(message, parse_mode='Markdown')


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show dictionary statistics (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ This command is only available to admins.")
        return
    
    dictionary = load_dictionary()
    
    total_words = len(dictionary)
    total_examples = sum(len(data['examples']) for data in dictionary.values())
    avg_examples = total_examples / total_words if total_words > 0 else 0
    
    await update.message.reply_text(
        f"📊 *Dictionary Statistics*\n\n"
        f"📖 Total Words: `{total_words}`\n"
        f"📝 Total Examples: `{total_examples}`\n"
        f"📈 Avg Examples/Word: `{avg_examples:.1f}`\n\n"
        f"Keep building! 🚀",
        parse_mode='Markdown'
    )


async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send dictionary backup file (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ This command is only available to admins.")
        return
    
    if os.path.exists(DICTIONARY_FILE):
        await update.message.reply_document(
            document=open(DICTIONARY_FILE, 'rb'),
            filename=f'dictionary_backup.json',
            caption="💾 Here's your dictionary backup!"
        )
    else:
        await update.message.reply_text("❌ No dictionary file found.")


async def search_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for word(s) in dictionary"""
    query = update.message.text.strip()
    
    # Split by comma for multiple words
    words = [w.strip().lower() for w in query.split(',')]
    
    dictionary = load_dictionary()
    
    if not dictionary:
        await update.message.reply_text(
            "📚 The dictionary is currently empty.\n\n"
            "Please wait while the admin adds some words! 😊"
        )
        return
    
    results = []
    not_found = []
    
    for word in words:
        if word in dictionary:
            data = dictionary[word]
            examples_formatted = '\n'.join([f"  • {ex}" for ex in data['examples']])
            
            result = (
                f"📖 *{word.title()}*\n\n"
                f"💡 *Meaning:*\n{data['meaning']}\n\n"
                f"📝 *Examples:*\n{examples_formatted}"
            )
            results.append(result)
        else:
            not_found.append(word)
    
    # Send results
    if results:
        response = "\n\n" + "─" * 30 + "\n\n"
        response = response.join(results)
        
        # Split if too long
        if len(response) > 4000:
            for result in results:
                await update.message.reply_text(result, parse_mode='Markdown')
        else:
            await update.message.reply_text(response, parse_mode='Markdown')
    
    if not_found:
        not_found_text = ', '.join([f"*{w}*" for w in not_found])
        await update.message.reply_text(
            f"❌ Word(s) not found: {not_found_text}\n\n"
            f"These words haven't been added to the dictionary yet. "
            f"Ask an admin to add them! 📚",
            parse_mode='Markdown'
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot"""
    # Get bot token from environment variable
    TOKEN = os.environ.get('BOT_TOKEN')
    
    if not TOKEN:
        print("❌ Error: BOT_TOKEN environment variable not set!")
        print("Please set your Telegram Bot Token:")
        print("export BOT_TOKEN='your_bot_token_here'")
        return
    
    # Load admin IDs from environment
    admin_ids_str = os.environ.get('ADMIN_IDS', '')
    if admin_ids_str:
        global ADMIN_IDS
        ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
        print(f"✅ Loaded {len(ADMIN_IDS)} admin ID(s)")
    else:
        print("⚠️  Warning: No ADMIN_IDS set. Admin features will be disabled.")
        print("Set ADMIN_IDS environment variable: export ADMIN_IDS='123456789,987654321'")
    
    # Start health check server in background (for Render Web Service)
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add conversation handler for adding words
    add_word_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_word_start)],
        states={
            WORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_word),
                CallbackQueryHandler(button_callback)
            ],
            MEANING: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_meaning)],
            EXAMPLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_examples)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_add),
            CallbackQueryHandler(button_callback, pattern="^cancel_add$")
        ],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(add_word_handler)
    application.add_handler(CommandHandler("delete", delete_word))
    application.add_handler(CommandHandler("list", list_words))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("backup", backup))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_words))
    application.add_error_handler(error_handler)
    
    # Start bot
    print("🚀 Bot is running!")
    print("Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
