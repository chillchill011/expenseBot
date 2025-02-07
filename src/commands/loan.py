from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

class LoanCommands:
    def __init__(self, sheet_service):
        self.sheet_service = sheet_service

    async def loan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text(
                    "❌ Format: /loan <amount> [description]\n"
                    "Example: /loan 5000 emi payment"
                )
                return

            amount = float(context.args[0])
            description = ' '.join(context.args[1:]) if len(context.args) > 1 else ""
            
            categories = await self.sheet_service.get_loan_categories()
            keyboard = self._create_loan_keyboard(amount, description, categories)
            
            await update.message.reply_text(
                "Select loan category:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid amount format")
        except Exception as e:
            print(f"Error in loan command: {e}")
            await update.message.reply_text("❌ Error processing loan")

    def _create_loan_keyboard(self, amount: float, description: str, categories: list):
        keyboard = []
        row = []
        for idx, cat in enumerate(categories):
            category, bank = cat[0], cat[1]
            callback_data = f"loan_{amount}_{category}"
            if description:
                callback_data += f"_{description}"
            button = InlineKeyboardButton(f"{category} ({bank})", callback_data=callback_data)
            row.append(button)
            if len(row) == 2 or idx == len(categories) - 1:
                keyboard.append(row)
                row = []
        return keyboard

    async def compare_loans(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("Current Month", callback_data="loan_compare_month")],
            [InlineKeyboardButton("Current Year", callback_data="loan_compare_year")],
            [InlineKeyboardButton("All Time Summary", callback_data="loan_compare_all")]
        ]
        await update.message.reply_text(
            "📊 Select loan comparison type:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_loan_callback(self, query):
        if query.data.startswith('loan_compare_'):
            await self._handle_loan_comparison(query)
        else:
            await self._handle_loan_addition(query)