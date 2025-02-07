from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.utils.constants import SUCCESS_MESSAGE, ERROR_MESSAGE

class InvestmentCommands:
    def __init__(self, sheet_service, category_service):
        self.sheet_service = sheet_service
        self.category_service = category_service

    async def invest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text(
                    "❌ Format: /invest <amount> [description]\n"
                    "Example: /invest 1000 stock purchase"
                )
                return

            amount = float(context.args[0])
            description = ' '.join(context.args[1:]) if len(context.args) > 1 else ""
            
            categories = await self.sheet_service.get_investment_categories()
            keyboard = self._create_investment_keyboard(amount, description, categories)
            
            await update.message.reply_text(
                "Select investment category:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except ValueError:
            await update.message.reply_text("❌ Invalid amount format")
        except Exception as e:
            print(f"Error in invest command: {e}")
            await update.message.reply_text("❌ Error processing investment")

    def _create_investment_keyboard(self, amount: float, description: str, categories: list) -> list:
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
        return keyboard

    async def compare_investments(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("Current Month", callback_data="inv_compare_month")],
            [InlineKeyboardButton("Current Year", callback_data="inv_compare_year")],
            [InlineKeyboardButton("Year-to-Year", callback_data="inv_compare_years")]
        ]
        
        await update.message.reply_text(
            "📊 Select investment comparison:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_investment_callback(self, query: CallbackQuery):
        if query.data.startswith('inv_compare_'):
            await self._handle_investment_comparison(query)
        else:
            await self._handle_investment_addition(query)