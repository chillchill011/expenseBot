from dotenv import load_dotenv
load_dotenv()
# Core bot implementation with essential components
import os
import asyncio
import nest_asyncio
from datetime import datetime, timedelta
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
            "• /edit - Modify last entry\n"
            "• /delete - Remove last entry\n"
            "• /summary - View monthly summary\n"
            "• /compare - Compare expenses\n"
            "• /categories - Add expense to category\n"
            "• /view - View categories with expenses\n"
            "• /invest - Add investment\n"
            "• /inv_compare - View investment summary\n"
            "• /loan - Add loan data\n"
            "• /loan_compare - View loan summary\n"
        )
        await update.message.reply_text(welcome_message)

    async def loan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle loan command"""
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text(
                    "❌ Format: /loan <amount> [description]\n"
                    "Example: /loan 5000 emi payment"
                )
                return

            amount = float(context.args[0])
            description = ' '.join(context.args[1:]) if len(context.args) > 1 else ""
            
            # Get loan categories from Loan Master sheet
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Loan Master!A:D'
            ).execute()
            
            categories = result.get('values', [])[1:]  # Skip header
            
            # Create category keyboard
            keyboard = []
            row = []
            for idx, cat in enumerate(categories):
                category = cat[0]
                bank = cat[1]
                callback_data = f"loan_{amount}_{category}"
                if description:
                    callback_data += f"_{description}"
                button = InlineKeyboardButton(f"{category} ({bank})", callback_data=callback_data)
                row.append(button)
                
                if len(row) == 2 or idx == len(categories) - 1:
                    keyboard.append(row)
                    row = []
            
            await update.message.reply_text(
                "Select loan category:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except ValueError:
            await update.message.reply_text("❌ Invalid amount format")
        except Exception as e:
            print(f"Error in loan command: {e}")
            await update.message.reply_text("❌ Error processing loan repayment")

    async def compare_loans(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Compare loan repayments"""
        try:
            keyboard = [
                [InlineKeyboardButton("Current Month", callback_data="loan_compare_month")],
                [InlineKeyboardButton("Current Year", callback_data="loan_compare_year")],
                [InlineKeyboardButton("All Time Summary", callback_data="loan_compare_all")]
            ]
            
            await update.message.reply_text(
                "📊 Select loan comparison type:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            print(f"Error in loan comparison: {e}")
            await update.message.reply_text("❌ Error showing comparison options")


    def _ensure_investment_sheets_exist(self):
        """Ensure investment sheets exist with proper headers"""
        try:
            current_year = datetime.now().year
            year_sheet = f"{current_year} Overview"
            
            # Check if sheet exists
            sheet_metadata = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            existing_sheets = sheet_metadata.get('sheets', [])
            sheet_exists = any(
                sheet['properties']['title'] == year_sheet 
                for sheet in existing_sheets
            )

            if not sheet_exists:
                print(f"Creating new investment sheet for {year_sheet}")
                # Create yearly overview sheet
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': year_sheet
                        }
                    }
                }]
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()

                # Add headers
                headers = [['Date', 'Amount', 'Category', 'User', 'Description', 'Returns', 'Return Date']]
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{year_sheet}!A1:G1',
                    valueInputOption='USER_ENTERED',
                    body={'values': headers}
                ).execute()
                
                print(f"Created investment sheet {year_sheet} with headers")
                
            return True
                
        except Exception as e:
            print(f"Error ensuring investment sheet exists: {e}")
            raise


    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages"""
        try:
            print(f"Received message in chat type: {update.message.chat.type}")  # Debug print
            text = update.message.text.strip()
            
            if update.message.chat.type in ['group', 'supergroup']:
                print(f"Group message: {text}")  # Debug print
                # Only process if message starts with a number
                if text and any(text.startswith(str(i)) for i in range(10)):
                    await self.handle_expense(update, context)
                else:
                    print("Message doesn't start with number, ignoring")  # Debug print
            else:
                print(f"Private message: {text}")  # Debug print
                await self.handle_expense(update, context)
                
        except Exception as e:
            print(f"Error in handle_message: {e}")

    async def invest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle investment command"""
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text(
                    "❌ Format: /invest <amount> [description]\n"
                    "Example: /invest 1000 stock purchase"
                )
                return

            amount = float(context.args[0])
            description = ' '.join(context.args[1:]) if len(context.args) > 1 else ""
            
            # Get investment categories from Investment Master sheet
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Investment Master!A:C'
            ).execute()
            
            categories = result.get('values', [])[1:]  # Skip header
            
            # Create category keyboard
            keyboard = []
            row = []
            for idx, cat in enumerate(categories):
                category = cat[0]
                risk = cat[1]
                callback_data = f"invest_{amount}_{category}"
                if description:
                    callback_data += f"_{description}"
                button = InlineKeyboardButton(f"{category} ({risk})", callback_data=callback_data)
                row.append(button)
                
                if len(row) == 2 or idx == len(categories) - 1:
                    keyboard.append(row)
                    row = []
            
            await update.message.reply_text(
                "Select investment category:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except ValueError:
            await update.message.reply_text("❌ Invalid amount format")
        except Exception as e:
            print(f"Error in invest command: {e}")
            await update.message.reply_text("❌ Error processing investment")


    async def compare_investments(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Compare investments across years"""
        try:
            keyboard = [
                [InlineKeyboardButton("Current Month", callback_data="inv_compare_month")],
                [InlineKeyboardButton("Current Year", callback_data="inv_compare_year")],
                [InlineKeyboardButton("Year-to-Year", callback_data="inv_compare_years")]
            ]
            
            await update.message.reply_text(
                "📊 Select investment comparison:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            print(f"Error in investment comparison: {e}")
            await update.message.reply_text("❌ Error showing comparison options")


    async def compare_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Compare expenses across different time periods"""
        try:
            keyboard = [
                [InlineKeyboardButton("Current vs Last Month", callback_data="compare_last_1")],
                [InlineKeyboardButton("Last Month vs Previous", callback_data="compare_last_2")],
                [InlineKeyboardButton("Current Year Monthly", callback_data="compare_year")]
            ]
            
            await update.message.reply_text(
                "📊 Select comparison type:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            print(f"Error in compare_expenses: {e}")
            await update.message.reply_text("❌ Error showing comparison options.")


    async def show_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show expense summary for different periods"""
        try:
            keyboard = [
                [InlineKeyboardButton("Current Month", callback_data="summary_current")],
                [InlineKeyboardButton("Last Month", callback_data="summary_last")],
                [InlineKeyboardButton("Last 3 Months", callback_data="summary_last3")],
                [InlineKeyboardButton("Current Year", callback_data="summary_year")],
                [InlineKeyboardButton("Last Year", callback_data="summary_lastyear")]
            ]
            
            await update.message.reply_text(
                "📈 Select period for summary:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            print(f"Error in show_summary: {e}")
            await update.message.reply_text("❌ Error showing summary options.")


    def _get_month_data(self, year_month: str) -> dict:
        """Get expense data for a specific month"""
        try:
            print(f"Getting data for month: {year_month}")  # Debug print
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{year_month}!A:E'
            ).execute()
            
            values = result.get('values', [])
            print(f"Retrieved values: {values}")  # Debug print
            
            if len(values) <= 1:  # Only headers or empty
                return {'total': 0, 'users': {}}
                
            total = 0
            users = {}
            
            for row in values[1:]:  # Skip header
                if len(row) >= 2:  # Make sure row has enough columns
                    try:
                        amount = float(row[1])
                        user = row[4] if len(row) > 4 else "Unknown"
                        total += amount
                        users[user] = users.get(user, 0) + amount
                    except (ValueError, IndexError) as e:
                        print(f"Error processing row {row}: {e}")  # Debug print
                        continue
                
            result_data = {'total': total, 'users': users}
            print(f"Processed data: {result_data}")  # Debug print
            return result_data
            
        except Exception as e:
            print(f"Error getting month data for {year_month}: {e}")  # Debug print
            return {'total': 0, 'users': {}}

    def _get_relative_month(self, months_back: int) -> str:
        """Get YYYY-MM for x months back"""
        current = datetime.now()
        relative_month = current.replace(day=1) - timedelta(days=1)
        for _ in range(months_back-1):
            relative_month = relative_month.replace(day=1) - timedelta(days=1)
        return relative_month.strftime('%Y-%m')


    async def view_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            current_month = datetime.now().strftime('%Y-%m')
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:E'
            ).execute()
            
            values = result.get('values', [])
            category_totals = {}
            
            # Calculate totals with error handling
            for row in values[1:]:  # Skip header
                try:
                    if len(row) >= 4:
                        category = row[3]
                        amount = float(row[1] if row[1] else 0)
                        category_totals[category] = category_totals.get(category, 0) + amount
                except (ValueError, IndexError):
                    continue
            
            keyboard = []
            row = []
            unique_categories = sorted(set(self.categories.values()))
            
            for idx, category in enumerate(unique_categories):
                if category:  # Skip empty categories
                    emoji = self._get_category_emoji(category)
                    total = category_totals.get(category, 0)
                    button_text = f"{emoji} {category} (₹{total:.0f})"
                    callback_data = f"viewcat_{category}_0"
                    button = InlineKeyboardButton(button_text, callback_data=callback_data)
                    row.append(button)
                    
                    if len(row) == 2 or idx == len(unique_categories) - 1:
                        keyboard.append(row)
                        row = []
            
            await update.message.reply_text(
                "📊 Select a category to view its expenses:\n"
                "(Shows category totals for current month)",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            print(f"Error in view_categories: {e}")
            await update.message.reply_text("❌ Error retrieving categories.")


    def _get_category_emoji(self, category: str) -> str:
        """Get emoji for category"""
        emoji_map = {
            'Groceries': '🛒',
            'Transportation': '🚗',
            'Entertainment': '🎬',
            'Utilities': '💡',
            'Health': '⚕️',
            'Shopping & Clothing': '👕',
            'Income': '💰',
            'Housing': '🏠',
            'Medical': '🏥',
            'Pet': '🐱',
            'Credit card': '💳',
            'Dining out': '🍽️',
        }
        return emoji_map.get(category, '📝')


    async def add_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add new item to category"""
        try:
            # Check if item name is provided
            if not context.args:
                await update.message.reply_text(
                    "❌ Please provide an item name.\n"
                    "Example: /category milk"
                )
                return

            item = ' '.join(context.args).lower()
            
            # Check if item already exists
            if item in self.categories:
                await update.message.reply_text(
                    f"📝 '{item}' is already mapped to category: {self.categories[item]}"
                )
                return

            # Get unique categories for keyboard
            unique_categories = sorted(set(self.categories.values()))
            keyboard = []
            row = []
            
            # Create keyboard with categories
            for idx, category in enumerate(unique_categories):
                callback_data = f"newcat_{item}_{category}"
                button = InlineKeyboardButton(category, callback_data=callback_data)
                row.append(button)
                
                if len(row) == 2 or idx == len(unique_categories) - 1:
                    keyboard.append(row)
                    row = []

            # Add option for new category
            keyboard.append([InlineKeyboardButton("➕ Add New Category", callback_data=f"newcat_{item}_new")])
            
            await update.message.reply_text(
                f"📋 Select category for '{item}' or add new:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            print(f"Error in add_category: {e}")
            await update.message.reply_text("❌ Error processing category addition.")


    async def edit_last_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit the last expense entry"""
        try:
            current_month = datetime.now().strftime('%Y-%m')
            
            # Get last entry
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:E'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers
                await update.message.reply_text("No entries to edit!")
                return
                
            last_entry = values[-1]  # Get last row
            
            # Parse command arguments
            try:
                args = context.args  # Get arguments after /edit
                if not args or len(args) < 2:
                    await update.message.reply_text(
                        "Please use format: /edit <amount> <description>\n"
                        "Example: /edit 75 milk"
                    )
                    return
                    
                new_amount = float(args[0])
                new_description = ' '.join(args[1:])
                
                # Get category for new description
                new_category = self._get_category(new_description.lower())
                if not new_category:
                    new_category = last_entry[3]  # Keep old category if not found
                    
                # Create confirmation keyboard
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "Yes", 
                            callback_data=f"edit_yes_{len(values)-1}_{new_amount}_{new_description}_{new_category}"
                        ),
                        InlineKeyboardButton("No", callback_data="edit_no")
                    ]
                ]
                
                await update.message.reply_text(
                    f"⚠️ You are updating this entry:\n\n"
                    f"From:\n"
                    f"Amount: ₹{float(last_entry[1]):.2f}\n"
                    f"Description: {last_entry[2]}\n"
                    f"Category: {last_entry[3]}\n\n"
                    f"To:\n"
                    f"Amount: ₹{new_amount:.2f}\n"
                    f"Description: {new_description}\n"
                    f"Category: {new_category}\n\n"
                    f"Do you want to proceed?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid amount. Please use format:\n"
                    "/edit <amount> <description>\n"
                    "Example: /edit 75 milk"
                )
                
        except Exception as e:
            print(f"Error in edit_last_entry: {e}")
            await update.message.reply_text("Error accessing last entry.")

    async def delete_last_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete the last expense entry"""
        try:
            current_month = datetime.now().strftime('%Y-%m')
            
            # Get last entry
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:E'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers
                await update.message.reply_text("No entries to delete!")
                return
                
            last_entry = values[-1]  # Get last row
            
            # Create confirmation keyboard
            keyboard = [
                [
                    InlineKeyboardButton("Yes", callback_data=f"delete_yes_{len(values)-1}"),
                    InlineKeyboardButton("No", callback_data="delete_no")
                ]
            ]
            
            await update.message.reply_text(
                f"Do you want to delete this entry?\n\n"
                f"Date: {last_entry[0]}\n"
                f"Amount: ₹{float(last_entry[1]):.2f}\n"
                f"Description: {last_entry[2]}\n"
                f"Category: {last_entry[3]}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            print(f"Error in delete_last_entry: {e}")
            await update.message.reply_text("Error retrieving last entry.")

    def _get_sheet_id(self, sheet_name: str) -> int:
        """Get sheet ID by name."""
        sheets = self.sheets_service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id
        ).execute()['sheets']
        
        for sheet in sheets:
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']
        return None


    def _ensure_investment_sheets_exist(self):
        """Ensure investment sheets exist with proper headers"""
        try:
            current_year = datetime.now().year
            year_sheet = f"{current_year} Overview"
            
            # Check if sheet exists
            sheet_metadata = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            existing_sheets = sheet_metadata.get('sheets', [])
            sheet_exists = any(
                sheet['properties']['title'] == year_sheet 
                for sheet in existing_sheets
            )

            if not sheet_exists:
                print(f"Creating new investment sheet for {year_sheet}")
                # Create yearly overview sheet
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': year_sheet
                        }
                    }
                }]
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()

                # Add headers
                headers = [['Date', 'Amount', 'Category', 'User', 'Description', 'Returns', 'Return Date']]
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{year_sheet}!A1:G1',
                    valueInputOption='USER_ENTERED',
                    body={'values': headers}
                ).execute()
                
                print(f"Created investment sheet {year_sheet} with headers")
            
            return True
                
        except Exception as e:
            print(f"Error ensuring investment sheet exists: {e}")
            raise


    def _ensure_monthly_sheet_exists(self):
        """Ensure the current month's sheet exists with proper headers."""
        try:
            current_month = datetime.now().strftime('%Y-%m')
            print(f"Checking for sheet: {current_month}")

            # Get all existing sheets
            sheet_metadata = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            # Check if current month sheet exists
            existing_sheets = sheet_metadata.get('sheets', [])
            sheet_exists = any(
                sheet['properties']['title'] == current_month 
                for sheet in existing_sheets
            )

            if not sheet_exists:
                print(f"Creating new sheet for {current_month}")
                # Create new sheet
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': current_month
                        }
                    }
                }]
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()

                # Add headers
                headers = [['Date', 'Amount', 'Description', 'Category', 'User', 'Details']]
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{current_month}!A1:E1',
                    valueInputOption='USER_ENTERED',
                    body={'values': headers}
                ).execute()
                
                print(f"Created new sheet for {current_month} with headers")
                
            return True
            
        except Exception as e:
            print(f"Error ensuring monthly sheet exists: {e}")
            raise

    async def handle_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = update.message.text
            
            # Extract amount
            parts = text.split()
            amount = float(parts[0])
            
            # Description is the first word after amount
            description = parts[1]
            
            # Everything after description becomes details
            details = ' '.join(parts[2:]) if len(parts) > 2 else ""
            
            category = self._get_category(description.lower())
            
            if not category:
                keyboard = self._create_category_keyboard(description, amount)
                await update.message.reply_text("📝 Select category:", reply_markup=InlineKeyboardMarkup(keyboard))
                return
            
            self._add_expense(
                amount=amount, 
                description=description, 
                category=category, 
                user=update.effective_user.username or "Unknown", 
                details=details
            )
            
            msg = f"✅ Added:\nAmount: ₹{amount:.2f}\nDescription: {description}"
            msg += f"\nCategory: {category}"
            if details:
                msg += f"\nDetails: {details}"
            
            await update.message.reply_text(msg)
        
        except ValueError:
            await update.message.reply_text("❌ Invalid amount format")
        except Exception as e:
            print(f"Error: {e}")
            await update.message.reply_text("❌ Error adding expense")

    def _load_categories(self) -> dict:
        """Load categories from master sheet."""
        try:
            print(f"Attempting to access sheet with ID: {self.spreadsheet_id}")
            result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range='Master!A2:B'
             ).execute()
            print("Successfully accessed sheet")
            print(f"Retrieved data: {result}")
        
            categories = {}
            for row in result.get('values', []):
                if len(row) >= 2:
                    expense, category = row
                    categories[expense.lower()] = category
        
            print(f"Processed categories: {categories}")
            return categories
        
        except Exception as e:
            print(f"Error accessing sheet: {e}")
            print(f"Using spreadsheet ID: {self.spreadsheet_id}")
            print(f"Service account email: {self.credentials.service_account_email}")
            raise

    def _get_category(self, description: str) -> str:
        """Get category for expense description."""
        description = description.lower()
        
        # Check for exact match first
        if description in self.categories:
            return self.categories[description]
        
        # Check if any part of description matches a category
        for key in self.categories.keys():
            if key in description:
                return self.categories[key]
        
        return None

    def _add_expense(self, amount: float, description: str, category: str, user: str, details: str = ""):
        try:
            current_month = datetime.now().strftime('%Y-%m')
            date = datetime.now().strftime('%d/%m/%Y')
            
            values = [[date, amount, description, category, user, details]]
            print(f"Adding to sheet {current_month}: {values}")
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:F',
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': values}
            ).execute()
            
            return True
                
        except Exception as e:
            print(f"Error in _add_expense:")
            print(f"- Sheet ID: {self.spreadsheet_id}")
            print(f"- Month: {current_month}")
            print(f"- Error: {str(e)}")
            raise


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
            # Existing category handling code
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
                f"Amount: ₹{amount:.2f}\n"
                f"Description: {description}\n"
                f"Category: {category}"
            )
            
        elif query.data.startswith('delete_'):
            action = query.data.split('_')[1]
            if action == 'yes':
                row = query.data.split('_')[2]
                try:
                    current_month = datetime.now().strftime('%Y-%m')
                    # Delete the row
                    requests = [{
                        'deleteDimension': {
                            'range': {
                                'sheetId': self._get_sheet_id(current_month),
                                'dimension': 'ROWS',
                                'startIndex': int(row),
                                'endIndex': int(row) + 1
                            }
                        }
                    }]
                    
                    self.sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body={'requests': requests}
                    ).execute()
                    
                    await query.edit_message_text("✅ Entry deleted successfully!")
                    
                except Exception as e:
                    print(f"Error deleting entry: {e}")
                    await query.edit_message_text("❌ Error deleting entry.")
            else:
                await query.edit_message_text("Deletion cancelled.")
                
        elif query.data.startswith('edit_'):
            parts = query.data.split('_')
            action = parts[1]
            if action == 'yes':
                try:
                    row = parts[2]
                    new_amount = parts[3]
                    new_description = parts[4]
                    new_category = parts[5]
                    current_month = datetime.now().strftime('%Y-%m')
                    
                    # Update the values
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'{current_month}!B{int(row)+1}:D{int(row)+1}',
                        valueInputOption='USER_ENTERED',
                        body={
                            'values': [[float(new_amount), new_description, new_category]]
                        }
                    ).execute()
                    
                    await query.edit_message_text("✅ Entry updated successfully!")
                    
                except Exception as e:
                    print(f"Error updating entry: {e}")
                    await query.edit_message_text("❌ Error updating entry.")
            else:
                await query.edit_message_text("Edit cancelled.")

        elif query.data.startswith('newcat_'):
            parts = query.data.split('_')
            item = parts[1]
            category = parts[2]
            
            try:
                if category == 'new':
                    # Store item temporarily and ask for new category name
                    context.user_data['pending_item'] = item
                    await query.edit_message_text(
                        f"📝 Please send the new category name for '{item}'"
                    )
                    return
                    
                # Add to master sheet
                self._add_category_mapping(item, category)
                
                await query.edit_message_text(
                    f"✅ Added mapping:\n"
                    f"Item: {item}\n"
                    f"Category: {category}"
                )
                
            except Exception as e:
                print(f"Error adding category: {e}")
                await query.edit_message_text("❌ Error adding category mapping.")

            # In button_handler method, update this section:
        elif query.data.startswith('view_cat_'):  # Changed this
            try:
                print(f"Processing view_cat callback: {query.data}")  # Debug print
                _, _, category, page = query.data.split('_')
                page = int(page)
                ITEMS_PER_PAGE = 10
                
                current_month = datetime.now().strftime('%Y-%m')
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{current_month}!A:E'
                ).execute()
                
                values = result.get('values', [])
                category_expenses = [row for row in values[1:] if row[3] == category]
                
                if not category_expenses:
                    await query.edit_message_text(
                        f"No expenses found for {category} this month.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ Back", callback_data="catlist_back")
                        ]])
                    )
                    return
                    
                total = sum(float(row[1]) for row in category_expenses)
                emoji = self._get_category_emoji(category)
                
                # Calculate pagination
                total_pages = (len(category_expenses) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
                start_idx = page * ITEMS_PER_PAGE
                end_idx = start_idx + ITEMS_PER_PAGE
                page_expenses = category_expenses[start_idx:end_idx]
                
                # Create message
                message = f"{emoji} {category} Expenses\n\n"
                message += f"Total: ₹{total:.2f}\n"
                message += f"Number of expenses: {len(category_expenses)}\n\n"
                
                for row in page_expenses:
                    date = row[0]
                    amount = float(row[1])
                    desc = row[2]
                    message += f"• {date}: ₹{amount:.2f} - {desc}\n"
                
                # Create navigation buttons
                keyboard = []
                nav_row = []
                
                if page > 0:
                    nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"view_cat_{category}_{page-1}"))
                
                nav_row.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore"))
                
                if page < total_pages - 1:
                    nav_row.append(InlineKeyboardButton("➡️", callback_data=f"view_cat_{category}_{page+1}"))
                    
                keyboard.append(nav_row)
                keyboard.append([InlineKeyboardButton("◀️ Back to Categories", callback_data="catlist_back")])
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            except Exception as e:
                print(f"Error viewing category: {e}")
                await query.edit_message_text("❌ Error retrieving category expenses.")

        elif query.data.startswith('loan_'):
            if query.data.startswith('loan_compare_'):
                try:
                    compare_type = query.data.split('_')[2]
                    message = "📊 Loan Repayment Summary\n\n"
                    
                    if compare_type == 'month':
                        # Current month summary
                        current_month = datetime.now().strftime('%m')
                        result = self.sheets_service.spreadsheets().values().get(
                            spreadsheetId=self.spreadsheet_id,
                            range='Loan Repayment!A:E'
                        ).execute()
                        
                        values = result.get('values', [])[1:]  # Skip header
                        current_month_payments = [
                            row for row in values 
                            if row[0].split('/')[1] == current_month
                        ]
                        
                        if current_month_payments:
                            total = sum(float(row[1]) for row in current_month_payments)
                            message += f"Current Month Total: ₹{total:.2f}\n"
                            message += f"Number of Payments: {len(current_month_payments)}\n\n"
                            
                            # Category breakdown
                            category_totals = {}
                            for row in current_month_payments:
                                category = row[3]  # Loan category
                                amount = float(row[1])
                                category_totals[category] = category_totals.get(category, 0) + amount
                            
                            message += "Category Breakdown:\n"
                            for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                                percentage = (amount / total * 100)
                                message += f"{category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
                        else:
                            message += "No loan payments this month"
                            
                    elif compare_type == 'year':
                        current_year = datetime.now().year
                        result = self.sheets_service.spreadsheets().values().get(
                            spreadsheetId=self.spreadsheet_id,
                            range='Loan Repayment!A:E'
                        ).execute()
                        
                        values = result.get('values', [])[1:]
                        year_payments = [
                            row for row in values 
                            if row[0].split('/')[0] == str(current_year)
                        ]
                        
                        if year_payments:
                            total = sum(float(row[1]) for row in year_payments)
                            message += f"Year {current_year} Total: ₹{total:.2f}\n"
                            message += f"Number of Payments: {len(year_payments)}\n\n"
                            
                            # Category breakdown
                            category_totals = {}
                            for row in year_payments:
                                category = row[3]
                                amount = float(row[1])
                                category_totals[category] = category_totals.get(category, 0) + amount
                            
                            message += "Category Breakdown:\n"
                            for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                                percentage = (amount / total * 100)
                                message += f"{category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
                        else:
                            message += "No loan payments this year"
                    
                    elif compare_type == 'all':
                        result = self.sheets_service.spreadsheets().values().get(
                            spreadsheetId=self.spreadsheet_id,
                            range='Loan Repayment!A:E'
                        ).execute()
                        
                        values = result.get('values', [])[1:]  # Skip header
                        if values:
                            # First, show overall total
                            total_all_time = sum(float(row[1]) for row in values)
                            message += f"📊 All Time Summary\n"
                            message += f"Total Payments: ₹{total_all_time:.2f}\n"
                            message += f"Number of Payments: {len(values)}\n"
                            message += "──────────────\n\n"
                            
                            # Group by years
                            year_data = {}
                            for row in values:
                                year = row[0].split('/')[0]  # Get year from date
                                if year not in year_data:
                                    year_data[year] = []
                                year_data[year].append(row)
                            
                            # Process each year
                            for year in sorted(year_data.keys(), reverse=True):
                                year_payments = year_data[year]
                                year_total = sum(float(row[1]) for row in year_payments)
                                
                                message += f"📅 Year {year}\n"
                                message += f"Total: ₹{year_total:.2f}\n"
                                message += f"Payments: {len(year_payments)}\n"
                                
                                # Category breakdown for this year
                                category_totals = {}
                                for row in year_payments:
                                    category = row[3]  # Loan category
                                    amount = float(row[1])
                                    category_totals[category] = category_totals.get(category, 0) + amount
                                
                                message += "\nCategory Breakdown:\n"
                                for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                                    percentage = (amount / year_total * 100)
                                    message += f"• {category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
                                
                                message += "──────────────\n"
                        else:
                            message += "No loan payment records found"
                    
                    await query.edit_message_text(
                        message,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ Back", callback_data="loan_compare_back")
                        ]])
                    )
                    
                except Exception as e:
                    print(f"Error in loan comparison: {e}")
                    await query.edit_message_text("❌ Error generating comparison")
                    
            else:
                try:
                    # Handle loan payment entry
                    parts = query.data.split('_')
                    amount = float(parts[1])
                    category = parts[2]
                    description = '_'.join(parts[3:]) if len(parts) > 3 else ""
                    
                    date = datetime.now().strftime('%Y/%m/%d')
                    values = [[
                        date,           # Date
                        amount,         # Amount
                        query.from_user.username or "Unknown",  # User
                        category,       # Loan category
                        description,    # Description
                    ]]
                    
                    self.sheets_service.spreadsheets().values().append(
                        spreadsheetId=self.spreadsheet_id,
                        range='Loan Repayment!A:E',
                        valueInputOption='USER_ENTERED',
                        insertDataOption='INSERT_ROWS',
                        body={'values': values}
                    ).execute()
                    
                    msg = f"✅ Loan Payment Added:\n"
                    msg += f"Amount: ₹{amount:.2f}\n"
                    msg += f"Category: {category}"
                    if description:
                        msg += f"\nDescription: {description}"
                    
                    await query.edit_message_text(msg)
                    
                except Exception as e:
                    print(f"Error adding loan payment: {e}")
                    await query.edit_message_text("❌ Error adding loan payment")


        elif query.data.startswith('compare_'):
            try:
                comparison_type = query.data.split('_')[1:]
                current_month = datetime.now().strftime('%Y-%m')
                last_month = self._get_relative_month(1)
                
                # Get data
                current_data = self._get_month_data(current_month)
                last_data = self._get_month_data(last_month)
                
                # Initialize message
                message = "📊 Expense Comparison\n\n"
                
                # Add current month data
                message += f"Current Month ({current_month})\n"
                message += f"Total: ₹{current_data['total']:.2f}\n\n"
                
                # Add last month data
                message += f"Last Month ({last_month})\n"
                message += f"Total: ₹{last_data['total']:.2f}\n\n"
                
                # Calculate change
                if last_data['total'] > 0:
                    diff = current_data['total'] - last_data['total']
                    pct = (diff / last_data['total']) * 100
                    message += f"{'📈' if diff > 0 else '📉'} Change: {pct:+.1f}%"
                else:
                    message += "No expenses in last month for comparison"
                    
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Back", callback_data="compare_back")
                    ]])
                )
            except Exception as e:
                print(f"Comparison error: {e}")
                await query.edit_message_text(
                    "❌ Error generating comparison",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Back", callback_data="compare_back")
                    ]])
                )

            
        elif query.data.startswith('summary_'):
            period = query.data.split('_')[1]
            message = "📈 Expense Summary\n\n"
            
            if period == 'current':
                month = datetime.now().strftime('%Y-%m')
                data = self._get_month_data(month)
                message += f"Current Month ({month})\n"
                message += f"Total Expenses: ₹{data['total']:.2f}\n\n"
                message += "By User:\n"
                for user, amount in data['users'].items():
                    message += f"{user}: ₹{amount:.2f}\n"
                    
            elif period == 'last':
                month = self._get_relative_month(1)
                data = self._get_month_data(month)
                message += f"Last Month ({month})\n"
                message += f"Total Expenses: ₹{data['total']:.2f}\n\n"
                message += "By User:\n"
                for user, amount in data['users'].items():
                    message += f"{user}: ₹{amount:.2f}\n"
                    
            elif period == 'last3':
                message = "Last 3 Months:\n\n"
                total = 0
                for i in range(3):
                    month = self._get_relative_month(i)
                    data = self._get_month_data(month)
                    message += f"{month}: ₹{data['total']:.2f}\n"
                    total += data['total']
                message += f"\nTotal: ₹{total:.2f}"
                
            elif period in ['year', 'lastyear']:
                year = datetime.now().year if period == 'year' else datetime.now().year - 1
                message = f"{year} Summary:\n\n"
                total = 0
                for month in range(1, 13):
                    month_str = f"{year}-{month:02d}"
                    data = self._get_month_data(month_str)
                    if data['total'] > 0:
                        message += f"{month_str}: ₹{data['total']:.2f}\n"
                        total += data['total']
                message += f"\nTotal: ₹{total:.2f}"
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Back", callback_data="summary_back")
                ]])
            )
        
        elif query.data.startswith('invest_'):
                    try:
                        # Parse callback data
                        parts = query.data.split('_')
                        amount = float(parts[1])
                        category = parts[2]
                        description = '_'.join(parts[3:]) if len(parts) > 3 else ""
                        
                        # Get current year sheet
                        current_year = datetime.now().year
                        year_sheet = f"{current_year} Overview"
                        
                        # Ensure sheet exists
                        self._ensure_investment_sheets_exist()
                        
                        # Add investment
                        date = datetime.now().strftime('%Y/%m/%d')
                        values = [[
                            date,           # Date
                            amount,         # Amount
                            category,       # Category
                            query.from_user.username or "Unknown",  # User
                            description,    # Description
                            "",            # Returns (empty initially)
                            ""             # Return Date (empty initially)
                        ]]
                        
                        self.sheets_service.spreadsheets().values().append(
                            spreadsheetId=self.spreadsheet_id,
                            range=f'{year_sheet}!A:G',
                            valueInputOption='USER_ENTERED',
                            insertDataOption='INSERT_ROWS',
                            body={'values': values}
                        ).execute()
                        
                        # Create success message
                        msg = f"✅ Investment Added:\n"
                        msg += f"Amount: ₹{amount:.2f}\n"
                        msg += f"Category: {category}"
                        if description:
                            msg += f"\nDescription: {description}"
                        
                        await query.edit_message_text(msg)
                        
                    except Exception as e:
                        print(f"Error adding investment: {e}")
                        await query.edit_message_text("❌ Error adding investment.")

        elif query.data.startswith('inv_compare_'):
            try:
                compare_type = query.data.split('_')[2]
                current_year = datetime.now().year
                message = "📊 Investment Comparison\n\n"
                
                if compare_type == 'month':
                    try:
                        # Current month comparison
                        current_month = datetime.now().strftime('%m')  # Get current month
                        result = self.sheets_service.spreadsheets().values().get(
                            spreadsheetId=self.spreadsheet_id,
                            range=f'{current_year} Overview!A:G'
                        ).execute()
                        
                        values = result.get('values', [])
                        if len(values) <= 1:
                            message += "No investments found for current month"
                        else:
                            values = values[1:]  # Skip header
                            # Filter current month investments
                            current_month_investments = []
                            for row in values:
                                try:
                                    if len(row) > 0:
                                        date_parts = row[0].split('/')
                                        if len(date_parts) >= 2 and date_parts[1] == current_month:
                                            current_month_investments.append(row)
                                except (IndexError, AttributeError):
                                    continue

                            if not current_month_investments:
                                message += "No investments found for current month"
                            else:
                                # Calculate total
                                total = sum(float(row[1]) for row in current_month_investments if len(row) > 1 and row[1])
                                message += f"Current Month Total: ₹{total:.2f}\n"
                                message += f"Number of Investments: {len(current_month_investments)}\n\n"
                                
                                # Category-wise breakdown
                                category_totals = {}
                                for row in current_month_investments:
                                    if len(row) >= 3:  # Ensure category exists
                                        category = row[2]
                                        try:
                                            amount = float(row[1]) if row[1] else 0
                                            category_totals[category] = category_totals.get(category, 0) + amount
                                        except ValueError:
                                            continue
                                
                                if category_totals:
                                    message += "Category Breakdown:\n"
                                    for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                                        percentage = (amount / total * 100) if total > 0 else 0
                                        message += f"{category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
                                    
                    except Exception as e:
                        print(f"Error in monthly calculation: {e}")
                        message += "Error processing monthly data"
                        
                elif compare_type == 'year':
                    try:
                        result = self.sheets_service.spreadsheets().values().get(
                            spreadsheetId=self.spreadsheet_id,
                            range=f'{current_year} Overview!A:G'
                        ).execute()
                        
                        values = result.get('values', [])
                        if len(values) <= 1:
                            message += f"No investments found for {current_year}"
                        else:
                            values = values[1:]  # Skip header
                            total_invested = 0
                            total_returns = 0
                            category_totals = {}
                            
                            for row in values:
                                try:
                                    if len(row) >= 2 and row[1]:
                                        amount = float(row[1])
                                        total_invested += amount
                                        # Add to category total
                                        if len(row) >= 3:
                                            category = row[2]
                                            category_totals[category] = category_totals.get(category, 0) + amount
                                    if len(row) >= 6 and row[5]:
                                        total_returns += float(row[5])
                                except (ValueError, IndexError):
                                    continue
                            
                            message += f"Year {current_year}:\n"
                            message += f"Total Invested: ₹{total_invested:.2f}\n"
                            message += f"Total Returns: ₹{total_returns:.2f}\n"
                            if total_invested > 0:
                                roi = (total_returns / total_invested) * 100
                                message += f"ROI: {roi:.1f}%\n\n"
                            
                            if category_totals:
                                message += "Category Breakdown:\n"
                                for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                                    percentage = (amount / total_invested * 100) if total_invested > 0 else 0
                                    message += f"{category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
                    
                    except Exception as e:
                        print(f"Error processing year data: {e}")
                        message += f"Error retrieving data for {current_year}"
                
                elif compare_type == 'years':
                    try:
                        # First get the investment summary
                        result = self.sheets_service.spreadsheets().values().get(
                            spreadsheetId=self.spreadsheet_id,
                            range='Investment Summary!A:E'
                        ).execute()
                        
                        # Also get all available sheets
                        sheet_metadata = self.sheets_service.spreadsheets().get(
                            spreadsheetId=self.spreadsheet_id
                        ).execute()
                        
                        # Find all Overview sheets
                        overview_sheets = [
                            sheet['properties']['title'] 
                            for sheet in sheet_metadata.get('sheets', [])
                            if 'Overview' in sheet['properties']['title']
                        ]
                        
                        overview_sheets.sort(reverse=True)  # Sort newest to oldest
                        
                        values = result.get('values', [])
                        if len(values) <= 1:
                            message += "No investment summary data available"
                        else:
                            values = values[1:]
                            sorted_values = sorted(values, key=lambda x: x[0], reverse=True)
                            
                            for sheet_name in overview_sheets:
                                try:
                                    year = sheet_name.split()[0]  # Get year from "YYYY Overview"
                                    
                                    # Get data from Investment Summary
                                    year_summary = next((row for row in sorted_values if row[0] == year), None)
                                    
                                    if year_summary:
                                        total_invested = float(year_summary[1]) if year_summary[1] else 0
                                        total_returns = float(year_summary[2]) if len(year_summary) > 2 and year_summary[2] else 0
                                        roi = float(year_summary[3]) if len(year_summary) > 3 and year_summary[3] else 0
                                        best_category = year_summary[4] if len(year_summary) > 4 else "N/A"
                                    else:
                                        # If no summary, calculate from Overview sheet
                                        year_result = self.sheets_service.spreadsheets().values().get(
                                            spreadsheetId=self.spreadsheet_id,
                                            range=f'{sheet_name}!A:G'
                                        ).execute()
                                        
                                        year_values = year_result.get('values', [])[1:]  # Skip header
                                        total_invested = sum(float(row[1]) for row in year_values if len(row) > 1 and row[1])
                                        total_returns = sum(float(row[5]) for row in year_values if len(row) > 5 and row[5])
                                        roi = (total_returns / total_invested * 100) if total_invested > 0 else 0
                                        best_category = "N/A"
                                    
                                    message += f"\n📅 Year {year}\n"
                                    message += f"Total Invested: ₹{total_invested:.2f}\n"
                                    message += f"Total Returns: ₹{total_returns:.2f}\n"
                                    message += f"ROI: {roi:.1f}%\n"
                                    message += f"Best Category: {best_category}\n"
                                    
                                    # Get category breakdown
                                    try:
                                        year_result = self.sheets_service.spreadsheets().values().get(
                                            spreadsheetId=self.spreadsheet_id,
                                            range=f'{sheet_name}!A:G'
                                        ).execute()
                                        
                                        year_values = year_result.get('values', [])[1:]  # Skip header
                                        category_totals = {}
                                        for year_row in year_values:
                                            if len(year_row) >= 3:
                                                category = year_row[2]
                                                amount = float(year_row[1]) if year_row[1] else 0
                                                category_totals[category] = category_totals.get(category, 0) + amount
                                        
                                        if category_totals:
                                            message += "\nCategory Breakdown:\n"
                                            for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                                                percentage = (amount / total_invested * 100) if total_invested > 0 else 0
                                                message += f"{category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
                                    except Exception as e:
                                        print(f"Error getting category breakdown for {sheet_name}: {e}")
                                        message += "\nCategory breakdown not available"
                                    
                                    message += "──────────────"
                                    
                                except Exception as e:
                                    print(f"Error processing sheet {sheet_name}: {e}")
                                    continue
                    
                    except Exception as e:
                        print(f"Error fetching investment summary: {e}")
                        message += "Error retrieving investment summary data"
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Back", callback_data="inv_compare_back")
                    ]])
                )
                
            except Exception as e:
                print(f"Error in investment comparison: {e}")
                await query.edit_message_text(
                    "❌ Error generating comparison",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Back", callback_data="inv_compare_back")
                    ]])
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


async def handle_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        
        # Extract amount
        parts = text.split()
        amount = float(parts[0])
        
        # Description is the first word after amount
        description = parts[1]
        
        # Everything after description becomes details
        details = ' '.join(parts[2:]) if len(parts) > 2 else ""
        
        category = self._get_category(description.lower())
        
        if not category:
            keyboard = self._create_category_keyboard(description, amount)
            await update.message.reply_text("📝 Select category:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        self._add_expense(
            amount=amount, 
            description=description, 
            category=category, 
            user=update.effective_user.username or "Unknown", 
            details=details
        )
        
        msg = f"✅ Added:\nAmount: ₹{amount:.2f}\nDescription: {description}"
        msg += f"\nCategory: {category}"
        if details:
            msg += f"\nDetails: {details}"
        
        await update.message.reply_text(msg)
    
    except ValueError:
        await update.message.reply_text("❌ Invalid amount format")
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("❌ Error adding expense")



async def main():
    try:
        # Load configuration
        token = os.getenv('TELEGRAM_TOKEN')
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        
        # Initialize bot
        bot = ExpenseBot(token, spreadsheet_id, credentials_path)
        
        # Create application with specific settings
        app = Application.builder().token(token).build()
        
        # Add handlers
        # Add command handlers first
        app.add_handler(CommandHandler("start", bot.start))
        app.add_handler(CommandHandler("delete", bot.delete_last_entry))
        app.add_handler(CommandHandler("edit", bot.edit_last_entry))
        app.add_handler(CommandHandler("category", bot.add_category))
        app.add_handler(CommandHandler("view", bot.view_categories))
        app.add_handler(CommandHandler("compare", bot.compare_expenses))
        app.add_handler(CommandHandler("summary", bot.show_summary))
        app.add_handler(CommandHandler("invest", bot.invest))
        app.add_handler(CommandHandler("inv_compare", bot.compare_investments))
        app.add_handler(CommandHandler("loan", bot.loan))
        app.add_handler(CommandHandler("loan_compare", bot.compare_loans))

        # Then add message handler for all text messages
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            bot.handle_message
        ))

        # Finally add callback handler
        app.add_handler(CallbackQueryHandler(bot.button_handler))

        print("Starting bot...")
        
        # Run with specific settings to avoid conflicts
        await app.run_polling(
            drop_pending_updates=True,
            close_loop=False,
            timeout=30,
            read_timeout=30,
            write_timeout=30
        )
        
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == '__main__':
    asyncio.run(main())