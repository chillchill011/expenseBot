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