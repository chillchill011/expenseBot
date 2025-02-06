import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

def ensure_sheets_exist():
    # Get credentials
    credentials = service_account.Credentials.from_service_account_file(
        os.getenv('GOOGLE_CREDENTIALS_PATH'),
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    
    sheets_service = build('sheets', 'v4', credentials=credentials)
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.strftime('%Y-%m')
    
    # Get existing sheets
    sheet_metadata = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()
    
    existing_sheets = [sheet['properties']['title'] for sheet in sheet_metadata.get('sheets', [])]
    
    # Check and create monthly expense sheet
    if current_month not in existing_sheets:
        print(f"Creating monthly sheet: {current_month}")
        requests = [{
            'addSheet': {
                'properties': {
                    'title': current_month
                }
            }
        }]
        
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': requests}
        ).execute()
        
        # Add headers
        headers = [['Date', 'Amount', 'Description', 'Category', 'User', 'Details']]
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{current_month}!A1:F1',
            valueInputOption='USER_ENTERED',
            body={'values': headers}
        ).execute()
    
    # Check and create yearly investment sheet
    year_sheet = f"{current_year} Overview"
    if year_sheet not in existing_sheets:
        print(f"Creating yearly investment sheet: {year_sheet}")
        requests = [{
            'addSheet': {
                'properties': {
                    'title': year_sheet
                }
            }
        }]
        
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': requests}
        ).execute()
        
        # Add headers
        headers = [['Date', 'Amount', 'Category', 'User', 'Description', 'Returns', 'Return Date']]
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{year_sheet}!A1:G1',
            valueInputOption='USER_ENTERED',
            body={'values': headers}
        ).execute()

if __name__ == '__main__':
    ensure_sheets_exist()