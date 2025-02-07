import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.modular')

# Bot configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH')

# Sheet names
MASTER_SHEET = 'Master'
INVESTMENT_MASTER = 'Investment Master'
LOAN_MASTER = 'Loan Master'

# Message templates
SUCCESS_MESSAGE = "✅ {}"
ERROR_MESSAGE = "❌ {}"