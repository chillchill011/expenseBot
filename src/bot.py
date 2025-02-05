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
            "• /view - View categories with expenses\n"
            "• /summary - View monthly summary\n"
            "• /compare - Compare expenses\n"
            "• /categories - Add expense to category\n"
            "• /edit - Modify last entry\n"
            "• /delete - Remove last entry"
        )
        await update.message.reply_text(welcome_message)


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
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{year_month}!A:E'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers or empty
                return {'total': 0, 'users': {}}
                
            total = 0
            users = {}
            
            for row in values[1:]:  # Skip header
                amount = float(row[1])
                user = row[4]
                total += amount
                users[user] = users.get(user, 0) + amount
                
            return {
                'total': total,
                'users': users
            }
        except Exception:
            return {'total': 0, 'users': {}}

    def _get_relative_month(self, months_back: int) -> str:
        """Get YYYY-MM for x months back"""
        current = datetime.now()
        relative_month = current.replace(day=1) - timedelta(days=1)
        for _ in range(months_back-1):
            relative_month = relative_month.replace(day=1) - timedelta(days=1)
        return relative_month.strftime('%Y-%m')


    async def view_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all categories and their expenses"""
        try:
            print("Starting view_categories function")  # Debug print
            # Get unique categories and their totals for current month
            current_month = datetime.now().strftime('%Y-%m')
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:E'
            ).execute()
            
            values = result.get('values', [])
            category_totals = {}
            
            # Calculate totals for each category
            for row in values[1:]:  # Skip header
                if len(row) >= 4:
                    category = row[3]
                    amount = float(row[1])
                    category_totals[category] = category_totals.get(category, 0) + amount
            
            # Create keyboard with categories and their totals
            keyboard = []
            row = []
            unique_categories = sorted(set(self.categories.values()))
            print(f"Found categories: {unique_categories}")  # Debug print
            
            for idx, category in enumerate(unique_categories):
                emoji = self._get_category_emoji(category)
                total = category_totals.get(category, 0)
                button_text = f"{emoji} {category} (${total:.0f})"
                callback_data = f"view_cat_{category}_0"  # Changed this
                print(f"Creating button with callback: {callback_data}")  # Debug print
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
                    f"Amount: ${float(last_entry[1]):.2f}\n"
                    f"Description: {last_entry[2]}\n"
                    f"Category: {last_entry[3]}\n\n"
                    f"To:\n"
                    f"Amount: ${new_amount:.2f}\n"
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
                f"Amount: ${float(last_entry[1]):.2f}\n"
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
                headers = [['Date', 'Amount', 'Description', 'Category', 'User']]
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
        """Handle regular expense messages."""
        try:
            text = update.message.text
            print(f"Processing message: {text}")  # Debug print
        
            try:
                # Try to split into amount and description
                first_word, *rest = text.split()
                amount = float(first_word)  # Try to convert first word to number
                description = ' '.join(rest)
            except ValueError:
                print(f"Invalid format: {text}")  # Debug print
                await update.message.reply_text(
                    "❌ Invalid format! Please use: <amount> <description>\n"
                    "Examples:\n"
                    "50 milk\n"
                    "100.50 uber\n"
                    "1500 rent"
                )
                return

            if not description:
                await update.message.reply_text("❌ Please provide a description for the expense!")
                return

            print(f"Amount: {amount}, Description: {description}")  # Debug print

            # Get category
            category = self._get_category(description.lower())
            print(f"Found category: {category}")  # Debug print

            if not category:
                keyboard = self._create_category_keyboard(description, amount)
                await update.message.reply_text(
                    "📝 Please select a category for this expense:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            # Add expense to sheet
            try:
                self._ensure_monthly_sheet_exists()  # Ensure sheet exists
                self._add_expense(
                    amount=amount,
                    description=description,
                    category=category,
                    user=update.effective_user.username or "Unknown"
                )
            
                # Success message with emoji
                await update.message.reply_text(
                    f"✅ Expense added successfully!\n\n"
                    f"Amount: ${amount:.2f}\n"
                    f"Description: {description}\n"
                    f"Category: {category}"
                )
            
            except Exception as e:
                print(f"Error adding expense to sheet: {e}")  # Debug print
                await update.message.reply_text(
                    "❌ Sorry, there was an error adding your expense. Please try again."
                )
                raise

        except Exception as e:
            print(f"Unexpected error in handle_expense: {e}")  # Debug print
            await update.message.reply_text(
                "❌ Something went wrong. Please try again with the format: <amount> <description>"
            )

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
        return self.categories.get(description)

    def _add_expense(self, amount: float, description: str, category: str, user: str):
        """Add expense to current month's sheet."""
        try:
            current_month = datetime.now().strftime('%Y-%m')
            date = datetime.now().strftime('%Y/%m/%d')
            
            values = [[date, amount, description, category, user]]
            print(f"Adding to sheet {current_month}: {values}")
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:E',
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': values}
            ).execute()
            
            print(f"Successfully added expense: {result}")
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
                f"Amount: ${amount:.2f}\n"
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
                message += f"Total: ${total:.2f}\n"
                message += f"Number of expenses: {len(category_expenses)}\n\n"
                
                for row in page_expenses:
                    date = row[0]
                    amount = float(row[1])
                    desc = row[2]
                    message += f"• {date}: ${amount:.2f} - {desc}\n"
                
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




        elif query.data.startswith('compare_'):
            try:
                comparison_type = query.data.split('_')[1:]
                message = ""  # Initialize message variable
                
                if query.data == "compare_back":
                    # Recreate comparison options
                    keyboard = [
                        [InlineKeyboardButton("Current vs Last Month", callback_data="compare_last_1")],
                        [InlineKeyboardButton("Last Month vs Previous", callback_data="compare_last_2")],
                        [InlineKeyboardButton("Current Year Monthly", callback_data="compare_year")]
                    ]
                    await query.edit_message_text(
                        "📊 Select comparison type:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
                
                if 'last_1' in comparison_type:
                    # Current vs Last Month
                    current_month = datetime.now().strftime('%Y-%m')
                    last_month = self._get_relative_month(1)
                    
                    current_data = self._get_month_data(current_month)
                    last_data = self._get_month_data(last_month)
                    
                    message = "📊 Month Comparison\n\n"
                    message += f"Current Month ({current_month}):\n"
                    message += f"Total: ${current_data['total']:.2f}\n\n"
                    message += f"Last Month ({last_month}):\n"
                    message += f"Total: ${last_data['total']:.2f}\n\n"
                    
                    if last_data['total'] != 0:
                        difference = current_data['total'] - last_data['total']
                        percentage = (difference / last_data['total'] * 100)
                        message += f"Difference: ${abs(difference):.2f}\n"
                        message += f"Change: {'+' if difference > 0 else ''}{percentage:.1f}%"
                    else:
                        message += "Unable to calculate difference (no data for last month)"
                    
                elif 'last_2' in comparison_type:
                    # Last Month vs Previous
                    last_month = self._get_relative_month(1)
                    previous_month = self._get_relative_month(2)
                    
                    last_data = self._get_month_data(last_month)
                    previous_data = self._get_month_data(previous_month)
                    
                    message = "📊 Previous Months Comparison\n\n"
                    message += f"Last Month ({last_month}):\n"
                    message += f"Total: ${last_data['total']:.2f}\n\n"
                    message += f"Previous Month ({previous_month}):\n"
                    message += f"Total: ${previous_data['total']:.2f}\n\n"
                    
                    if previous_data['total'] != 0:
                        difference = last_data['total'] - previous_data['total']
                        percentage = (difference / previous_data['total'] * 100)
                        message += f"Difference: ${abs(difference):.2f}\n"
                        message += f"Change: {'+' if difference > 0 else ''}{percentage:.1f}%"
                    else:
                        message += "Unable to calculate difference (no data for previous month)"
                    
                elif 'year' in comparison_type:
                    # Current Year Monthly
                    current_year = datetime.now().year
                    message = f"📅 {current_year} Monthly Totals\n\n"
                    
                    has_data = False
                    for month in range(1, 13):
                        month_str = f"{current_year}-{month:02d}"
                        data = self._get_month_data(month_str)
                        if data['total'] > 0:
                            has_data = True
                            message += f"{month_str}: ${data['total']:.2f}\n"
                    
                    if not has_data:
                        message += "No expenses recorded for this year yet."
                
                # Add back button
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Back", callback_data="compare_back")
                    ]])
                )
                
            except Exception as e:
                print(f"Error in comparison: {e}")
                await query.edit_message_text(
                    "❌ Error generating comparison.",
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
                message += f"Total Expenses: ${data['total']:.2f}\n\n"
                message += "By User:\n"
                for user, amount in data['users'].items():
                    message += f"{user}: ${amount:.2f}\n"
                    
            elif period == 'last':
                month = self._get_relative_month(1)
                data = self._get_month_data(month)
                message += f"Last Month ({month})\n"
                message += f"Total Expenses: ${data['total']:.2f}\n\n"
                message += "By User:\n"
                for user, amount in data['users'].items():
                    message += f"{user}: ${amount:.2f}\n"
                    
            elif period == 'last3':
                message = "Last 3 Months:\n\n"
                total = 0
                for i in range(3):
                    month = self._get_relative_month(i)
                    data = self._get_month_data(month)
                    message += f"{month}: ${data['total']:.2f}\n"
                    total += data['total']
                message += f"\nTotal: ${total:.2f}"
                
            elif period in ['year', 'lastyear']:
                year = datetime.now().year if period == 'year' else datetime.now().year - 1
                message = f"{year} Summary:\n\n"
                total = 0
                for month in range(1, 13):
                    month_str = f"{year}-{month:02d}"
                    data = self._get_month_data(month_str)
                    if data['total'] > 0:
                        message += f"{month_str}: ${data['total']:.2f}\n"
                        total += data['total']
                message += f"\nTotal: ${total:.2f}"
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Back", callback_data="summary_back")
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
    """Handle regular expense messages."""
    try:
        text = update.message.text
        print(f"Received message: {text}")  # Debug print
        
        amount, *description = text.split()
        amount = float(amount)
        description = ' '.join(description)
        
        # Get category
        category = self._get_category(description)
        print(f"Found category: {category}")  # Debug print
        
        if not category:
            # Ask user to choose category
            keyboard = self._create_category_keyboard(description, amount)
            await update.message.reply_text(
                "Please select a category:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Add expense to sheet
        try:
            self._add_expense(
                amount=amount,
                description=description,
                category=category,
                user=update.effective_user.username
            )
            print(f"Added expense: {amount} {description} {category}")  # Debug print
            
            await update.message.reply_text(
                f"Added expense:\n"
                f"Amount: ${amount:.2f}\n"
                f"Description: {description}\n"
                f"Category: {category}"
            )
        except Exception as e:
            print(f"Error adding expense to sheet: {e}")  # Debug print
            await update.message.reply_text(
                "Sorry, there was an error adding your expense. Please try again."
            )
            
    except ValueError as e:
        print(f"Value error: {e}")  # Debug print
        await update.message.reply_text(
            "Please use the format: <amount> <description>\n"
            "Example: 50 milk"
        )
    except Exception as e:
        print(f"Unexpected error: {e}")  # Debug print
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again."
        )




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
        app.add_handler(CommandHandler("start", bot.start))
        app.add_handler(CommandHandler("delete", bot.delete_last_entry))
        app.add_handler(CommandHandler("edit", bot.edit_last_entry))
        app.add_handler(CommandHandler("category", bot.add_category))
        app.add_handler(CommandHandler("view", bot.view_categories))
        app.add_handler(CommandHandler("compare", bot.compare_expenses))
        app.add_handler(CommandHandler("summary", bot.show_summary))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, bot.handle_expense
        ))
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