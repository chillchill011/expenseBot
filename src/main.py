import os
import asyncio
import nest_asyncio
import logging
from dotenv import load_dotenv
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters

from src.services.sheets import SheetService
from src.services.category_service import CategoryService
from src.commands.expense import ExpenseCommands
from src.commands.investment import InvestmentCommands
from src.commands.loan import LoanCommands

nest_asyncio.apply()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def main():
    try:
        load_dotenv('.env.modular')
        
        sheet_service = SheetService(
            os.getenv('SPREADSHEET_ID'),
            os.getenv('GOOGLE_CREDENTIALS_PATH')
        )
        category_service = CategoryService(sheet_service)
        
        # Initialize command handlers
        expense_commands = ExpenseCommands(sheet_service, category_service)
        investment_commands = InvestmentCommands(sheet_service, category_service)
        loan_commands = LoanCommands(sheet_service)
        
        app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
        
        # Add command handlers
        app.add_handler(CommandHandler("delete", expense_commands.delete_last_entry))
        app.add_handler(CommandHandler("edit", expense_commands.edit_last_entry))
        app.add_handler(CommandHandler("invest", investment_commands.invest))
        app.add_handler(CommandHandler("inv_compare", investment_commands.compare_investments))
        app.add_handler(CommandHandler("loan", loan_commands.loan))
        app.add_handler(CommandHandler("loan_compare", loan_commands.compare_loans))
        
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            expense_commands.handle_expense
        ))
        
        async def callback_handler(update, context):
            query = update.callback_query
            if query.data.startswith('invest_'):
                await investment_commands.handle_investment_callback(query)
            elif query.data.startswith('loan_'):
                await loan_commands.handle_loan_callback(query)
            else:
                await expense_commands.button_handler(update, context)
                
        app.add_handler(CallbackQueryHandler(callback_handler))
        
        print("Starting test bot...")
        await app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == '__main__':
    asyncio.run(main())