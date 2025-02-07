from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

class SheetService:
    def __init__(self, spreadsheet_id: str, credentials_path: str):
        self.spreadsheet_id = spreadsheet_id
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=self.credentials)

    async def add_expense(self, amount: float, description: str, category: str, user: str, details: str = ""):
        try:
            current_month = datetime.now().strftime('%Y-%m')
            date = datetime.now().strftime('%d/%m/%Y')
            
            values = [[date, amount, description, category, user, details]]
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:F',
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': values}
            ).execute()
            
            return True
        except Exception as e:
            print(f"Error adding expense: {e}")
            return False

    async def get_last_entry(self):
        try:
            current_month = datetime.now().strftime('%Y-%m')
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!A:F'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers
                return None
                
            last_row = values[-1]
            return {
                'row': len(values) - 1,
                'date': last_row[0],
                'amount': last_row[1],
                'description': last_row[2],
                'category': last_row[3],
                'user': last_row[4],
                'details': last_row[5] if len(last_row) > 5 else ""
            }
        except Exception as e:
            print(f"Error getting last entry: {e}")
            return None

    async def delete_row(self, row: int):
        try:
            current_month = datetime.now().strftime('%Y-%m')
            sheet_id = self._get_sheet_id(current_month)
            
            requests = [{
                'deleteDimension': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'ROWS',
                        'startIndex': row,
                        'endIndex': row + 1
                    }
                }
            }]
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            return True
        except Exception as e:
            print(f"Error deleting row: {e}")
            return False

    async def update_expense(self, row: int, amount: float, description: str, category: str):
        try:
            current_month = datetime.now().strftime('%Y-%m')
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f'{current_month}!B{row+1}:D{row+1}',
                valueInputOption='USER_ENTERED',
                body={
                    'values': [[amount, description, category]]
                }
            ).execute()
            
            return True
        except Exception as e:
            print(f"Error updating expense: {e}")
            return False

    def _get_sheet_id(self, sheet_name: str) -> int:
        sheets = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id
        ).execute()['sheets']
        
        for sheet in sheets:
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']
        return 
    

    async def get_investment_categories(self):
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range='Investment Master!A:C'
        ).execute()
        return result.get('values', [])[1:]  # Skip header

    async def add_investment(self, date: str, amount: float, category: str, 
                            user: str, description: str = ""):
        current_year = datetime.now().year
        year_sheet = f"{current_year} Overview"
        
        values = [[
            date, amount, category, user, description, "", ""  # Empty Returns and Return Date
        ]]
        
        return await self._append_values(f'{year_sheet}!A:G', values)