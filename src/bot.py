from dotenv import load_dotenv
load_dotenv()
# Core bot implementation with essential components
import os
import asyncio
import nest_asyncio
from datetime import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account

nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ExpenseBot:
    def __init__(self, token: str, spreadsheet_id: str, credentials_path: str):
        """Initialize bot with necessary credentials and configurations."""
        self.spreadsheet_id = spreadsheet_id
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
        
        # Initialize category cache
        self.categories = self._load_categories()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        welcome_message = (
            "Welcome to the Expense Tracker Bot!\n\n"
            "Commands:\n"
            "• Simply type amount and description (e.g., '50 milk')\n"
            "• /invest - Add investment\n"
            "• /missed - Add past expense\n"
            "• /summary - View monthly summary\n"
            "• /compare - Compare expenses\n"
            "• /categories - List categories\n"
            "• /edit - Modify entry\n"
            "• /delete - Remove entry"
        )
        await update.message.reply_text(welcome_message)

    async def handle_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular expense messages."""
        try:
            text = update.message.text
            amount, *description = text.split()
            amount = float(amount)
            description = ' '.join(description)
            
            # Get category
            category = self._get_category(description)
            
            if not category:
                # Ask user to choose category
                keyboard = self._create_category_keyboard(description, amount)
                await update.message.reply_text(
                    "Please select a category:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            
            # Add expense to sheet
            self._add_expense(
                amount=amount,
                description=description,
                category=category,
                user=update.effective_user.username
            )
            
            await update.message.reply_text(
                f"Added expense:\n"
                f"Amount: ${amount:.2f}\n"
                f"Description: {description}\n"
                f"Category: {category}"
            )
            
        except ValueError:
            await update.message.reply_text(
                "Please use the format: <amount> <description>\n"
                "Example: 50 milk"
            )

    def _load_categories(self) -> dict:
        """Load categories from master sheet."""
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range='Master!A2:B'
        ).execute()
        
        categories = {}
        for row in result.get('values', []):
            if len(row) >= 2:
                expense, category = row
                categories[expense.lower()] = category
        
        return categories

    def _get_category(self, description: str) -> str:
        """Get category for expense description."""
        description = description.lower()
        return self.categories.get(description)

    def _add_expense(self, amount: float, description: str, category: str, user: str):
        """Add expense to current month's sheet."""
        current_month = datetime.now().strftime('%Y-%m')
        date = datetime.now().strftime('%Y-%m-%d')
        
        values = [[date, amount, description, category, user]]
        
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f'{current_month}!A:E',
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': values}
        ).execute()

    def _create_category_keyboard(self, description: str, amount: float) -> list:
        """Create inline keyboard for category selection."""
        unique_categories = sorted(set(self.categories.values()))
        keyboard = []
        row = []
        
        for idx, category in enumerate(unique_categories):
            callback_data = f"cat_{description}_{amount}_{category}"
            button = InlineKeyboardButton(category, callback_data=callback_data)
            row.append(button)
            
            if len(row) == 2 or idx == len(unique_categories) - 1:
                keyboard.append(row)
                row = []
        
        return keyboard

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses."""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('cat_'):
            _, description, amount, category = query.data.split('_')
            amount = float(amount)
            
            # Add expense with selected category
            self._add_expense(
                amount=amount,
                description=description,
                category=category,
                user=query.from_user.username
            )
            
            # Update master sheet with new category mapping
            self._add_category_mapping(description, category)
            
            await query.edit_message_text(
                f"Added expense:\n"
                f"Amount: ${amount:.2f}\n"
                f"Description: {description}\n"
                f"Category: {category}"
            )

    def _add_category_mapping(self, description: str, category: str):
        """Add new category mapping to master sheet."""
        values = [[description.lower(), category]]
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range='Master!A:B',
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': values}
        ).execute()
        
        # Update local cache
        self.categories[description.lower()] = category

async def main():
    # Load configuration
    token = os.getenv('TELEGRAM_TOKEN')
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
    
    # Add error checking
    if not all([token, spreadsheet_id, credentials_path]):
        print("Error: Missing environment variables")
        print(f"TELEGRAM_TOKEN: {'Set' if token else 'Missing'}")
        print(f"SPREADSHEET_ID: {'Set' if spreadsheet_id else 'Missing'}")
        print(f"GOOGLE_CREDENTIALS_PATH: {'Set' if credentials_path else 'Missing'}")
        return
    
    # Initialize bot
    bot = ExpenseBot(token, spreadsheet_id, credentials_path)
    
    # Create application
    app = Application.builder().token(token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, bot.handle_expense
    ))
    app.add_handler(CallbackQueryHandler(bot.button_handler))
    
    print("Starting bot...")
    
    # Start the bot
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped gracefully")
    except Exception as e:
        print(f"Error running bot: {e}")