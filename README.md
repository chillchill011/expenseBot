Telegram Expense Tracker Bot
A comprehensive Telegram bot for tracking daily expenses, investments, and loan repayments using Google Sheets as a backend. This bot allows users in a group chat to log their financial activities seamlessly, with powerful reporting and data management features.

🌟 Features
Effortless Expense Logging: Add an expense by simply sending a message (e.g., 50 milk, 1L packet).

Smart Categorization: Automatically assigns a category to known items. For new items, it presents an interactive menu to choose a category.

Investment & Loan Tracking:

/invest <amount> [description] - Log a new investment.

/loan <amount> [description] - Log a loan repayment.

Historical Data Entry:

/add (as a reply to a message) - Add a past expense, investment, or loan using the original message's date and author.

Data Management:

/edit <amount> <description> - Modify the last logged entry.

/delete - Delete the very last entry with confirmation.

Dynamic Category Management:

/category <item name> - Map a new item to an existing or new category.

Powerful Reporting & Summaries:

/summary - Get expense summaries for the current/last month, last 3 months, or by year.

/compare - Compare expenses between different time periods.

/view - See a breakdown of expenses by category for the current month.

/inv_compare - Analyze investment performance (monthly, yearly, year-on-year).

/loan_compare - View loan repayment summaries (monthly, yearly, all-time).

Google Sheets Backend: All data is stored in a Google Sheet, giving you full ownership and easy access to your financial data.

Multi-User Support: Designed for group chats, it correctly attributes each entry to the user who logged it.

🛠️ Setup and Installation
Follow these steps to set up and run your own instance of the expense bot.

1. Prerequisites
Python 3.8+

A Telegram account

A Google Cloud Platform (GCP) account

2. Clone the Repository
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

3. Install Dependencies
Create a requirements.txt file with the following content:

python-telegram-bot
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
python-dotenv
nest_asyncio

Then, install the packages:

pip install -r requirements.txt

4. Google Cloud & Sheets Setup
Create a GCP Project: Go to the Google Cloud Console and create a new project.

Enable Google Sheets API: In your new project, go to "APIs & Services" > "Library" and enable the Google Sheets API.

Create a Service Account:

Go to "APIs & Services" > "Credentials".

Click "Create Credentials" > "Service account".

Give it a name (e.g., expense-bot-sheets-editor) and grant it the Editor role.

After creating the account, go to its "Keys" tab, click "Add Key" > "Create new key", select JSON, and download the credentials file.

Move Credentials File: Place the downloaded JSON file in your project directory.

5. Google Sheet Preparation
Create a new Google Sheet.

Share the Sheet: Click the "Share" button and add the service account's email address as an Editor. You can find this email in the downloaded JSON file under the client_email key.

Create Initial Sheets (Tabs): You must create the following tabs manually. The bot will create other sheets (like 2025-07) automatically.

Master:

Column A: Expense (e.g., milk)

Column B: Category (e.g., Groceries)

Investment Master:

Column A: Category (e.g., Stocks, Mutual Funds)

Column B: Risk (e.g., High, Medium)

Column C: Platform (e.g., Zerodha, Groww)

Loan Master:

Column A: Category (e.g., Home Loan, Car Loan)

Column B: Bank (e.g., HDFC, ICICI)

Loan Repayment:

Column A: Date

Column B: Amount

Column C: User

Column D: Category

Column E: Description

Investment Summary:

Column A: Year

Column B: Total Invested

Column C: Total Returns

Column D: ROI

Column E: Best Category

6. Telegram Bot Setup
Open Telegram and talk to the @BotFather.

Use the /newbot command to create a new bot.

BotFather will give you a token. Copy this token.

7. Configuration
Create a .env file in the root of your project directory and add the following variables:

TELEGRAM_TOKEN="YOUR_TELEGRAM_BOT_TOKEN_HERE"
SPREADSHEET_ID="YOUR_GOOGLE_SHEET_ID_HERE"
GOOGLE_CREDENTIALS_PATH="path/to/your/downloaded-credentials.json"

SPREADSHEET_ID: You can find this in the URL of your Google Sheet: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_IS_HERE/edit.

GOOGLE_CREDENTIALS_PATH: The name of the JSON file you downloaded in step 4.

8. Running the Bot
Finally, run the bot with the following command:

python "Expense Bot.py"

Add the bot to your Telegram group, and it's ready to start tracking!

🤖 How to Use
Start: Send /start to the bot to see a list of available commands.

Add Expense: Send a message in the format: <amount> <description>, [details].

Example: 150 Coffee, met with John

Example: 700 Groceries

Add Investment: Use the /invest command.

Example: /invest 5000 Nifty 50 Index Fund

Add Loan Payment: Use the /loan command.

Example: /loan 25000 Home Loan EMI

Use other commands like /summary, /compare, /edit, and /delete as needed. The bot will guide you with interactive buttons.
