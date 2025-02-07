from telegram import InlineKeyboardButton

class CategoryService:
    def __init__(self, sheet_service):
        self.sheet_service = sheet_service
        self.categories = self._load_categories()

    def _load_categories(self):
        """Load categories from master sheet"""
        try:
            result = self.sheet_service.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_service.spreadsheet_id,
                range='Master!A2:B'
            ).execute()
            
            categories = {}
            for row in result.get('values', []):
                if len(row) >= 2:
                    expense, category = row
                    categories[expense.lower()] = category
            return categories
            
        except Exception as e:
            print(f"Error loading categories: {e}")
            return {}

    def get_category(self, description: str) -> str:
        """Get category for description"""
        description = description.lower()
        
        # Check exact match
        if description in self.categories:
            return self.categories[description]
        
        # Check partial match
        for key in self.categories.keys():
            if key in description:
                return self.categories[key]
        return None

    def create_category_keyboard(self, description: str, amount: float) -> list:
        """Create category selection keyboard"""
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

    async def add_category_mapping(self, description: str, category: str):
        """Add new category mapping"""
        try:
            values = [[description.lower(), category]]
            self.sheet_service.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_service.spreadsheet_id,
                range='Master!A:B',
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': values}
            ).execute()
            
            # Update local cache
            self.categories[description.lower()] = category
            return True
        except Exception as e:
            print(f"Error adding category mapping: {e}")
            return False