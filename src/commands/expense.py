from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

class ExpenseCommands:
    def __init__(self, sheet_service, category_service):
        self.sheet_service = sheet_service
        self.category_service = category_service

    async def handle_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular expense messages"""
        try:
            if not update.message:
                return
                
            text = update.message.text
            parts = text.split()
            
            # Parse input
            amount = float(parts[0])
            description = parts[1]
            details = ' '.join(parts[2:]) if len(parts) > 2 else ""
            
            category = self.category_service.get_category(description.lower())
            
            if not category:
                keyboard = self.category_service.create_category_keyboard(description, amount)
                await update.message.reply_text(
                    "📝 Select category:", 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            
            success = await self.sheet_service.add_expense(
                amount=amount,
                description=description,
                category=category,
                user=update.effective_user.username or "Unknown",
                details=details
            )
            
            if success:
                msg = f"✅ Added:\nAmount: ₹{amount:.2f}\nDescription: {description}"
                msg += f"\nCategory: {category}"
                if details:
                    msg += f"\nDetails: {details}"
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("❌ Error adding expense")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid amount format")
        except Exception as e:
            print(f"Error in handle_expense: {e}")
            await update.message.reply_text("❌ Error adding expense")

    async def edit_last_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit last expense entry"""
        try:
            if not context.args or len(context.args) < 2:
                await update.message.reply_text(
                    "Please use format: /edit <amount> <description>\n"
                    "Example: /edit 75 milk"
                )
                return

            last_entry = await self.sheet_service.get_last_entry()
            if not last_entry:
                await update.message.reply_text("No entries to edit!")
                return

            new_amount = float(context.args[0])
            new_description = ' '.join(context.args[1:])
            new_category = self.category_service.get_category(new_description.lower()) or last_entry['category']

            keyboard = [[
                InlineKeyboardButton(
                    "Yes", 
                    callback_data=f"edit_yes_{last_entry['row']}_{new_amount}_{new_description}_{new_category}"
                ),
                InlineKeyboardButton("No", callback_data="edit_no")
            ]]

            message = (
                f"⚠️ You are updating this entry:\n\n"
                f"From:\n"
                f"Amount: ₹{float(last_entry['amount']):.2f}\n"
                f"Description: {last_entry['description']}\n"
                f"Category: {last_entry['category']}\n\n"
                f"To:\n"
                f"Amount: ₹{new_amount:.2f}\n"
                f"Description: {new_description}\n"
                f"Category: {new_category}\n\n"
                f"Do you want to proceed?"
            )

            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except ValueError:
            await update.message.reply_text("❌ Invalid amount format")
        except Exception as e:
            print(f"Error in edit_last_entry: {e}")
            await update.message.reply_text("Error accessing last entry")

    async def delete_last_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete last expense entry"""
        try:
            last_entry = await self.sheet_service.get_last_entry()
            if not last_entry:
                await update.message.reply_text("No entries to delete!")
                return

            keyboard = [[
                InlineKeyboardButton("Yes", callback_data=f"delete_yes_{last_entry['row']}"),
                InlineKeyboardButton("No", callback_data="delete_no")
            ]]

            await update.message.reply_text(
                f"Do you want to delete this entry?\n\n"
                f"Date: {last_entry['date']}\n"
                f"Amount: ₹{float(last_entry['amount']):.2f}\n"
                f"Description: {last_entry['description']}\n"
                f"Category: {last_entry['category']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            print(f"Error in delete_last_entry: {e}")
            await update.message.reply_text("Error retrieving last entry")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks for expenses"""
        query = update.callback_query
        await query.answer()

        if query.data.startswith('delete_'):
            await self._handle_delete_callback(query)
        elif query.data.startswith('edit_'):
            await self._handle_edit_callback(query)
        elif query.data.startswith('cat_'):
            await self._handle_category_callback(query)

    async def _handle_delete_callback(self, query):
        """Handle delete confirmation callback"""
        try:
            action = query.data.split('_')[1]
            if action == 'yes':
                row = query.data.split('_')[2]
                success = await self.sheet_service.delete_row(int(row))
                
                if success:
                    await query.edit_message_text("✅ Entry deleted successfully!")
                else:
                    await query.edit_message_text("❌ Error deleting entry.")
            else:
                await query.edit_message_text("Deletion cancelled.")
        except Exception as e:
            print(f"Error in delete callback: {e}")
            await query.edit_message_text("❌ Error deleting entry.")

    async def _handle_edit_callback(self, query):
        """Handle edit confirmation callback"""
        try:
            parts = query.data.split('_')
            action = parts[1]
            if action == 'yes':
                row = int(parts[2])
                new_amount = float(parts[3])
                new_description = parts[4]
                new_category = parts[5]
                
                success = await self.sheet_service.update_expense(
                    row=row,
                    amount=new_amount,
                    description=new_description,
                    category=new_category
                )
                
                if success:
                    await query.edit_message_text("✅ Entry updated successfully!")
                else:
                    await query.edit_message_text("❌ Error updating entry.")
            else:
                await query.edit_message_text("Edit cancelled.")
        except Exception as e:
            print(f"Error in edit callback: {e}")
            await query.edit_message_text("❌ Error updating entry.")

    async def _handle_category_callback(self, query):
        """Handle category selection callback"""
        try:
            _, description, amount, category = query.data.split('_')
            amount = float(amount)
            
            success = await self.sheet_service.add_expense(
                amount=amount,
                description=description,
                category=category,
                user=query.from_user.username or "Unknown"
            )
            
            if success:
                await self.category_service.add_category_mapping(description, category)
                await query.edit_message_text(
                    f"Added expense:\n"
                    f"Amount: ₹{amount:.2f}\n"
                    f"Description: {description}\n"
                    f"Category: {category}"
                )
            else:
                await query.edit_message_text("❌ Error adding expense.")
        except Exception as e:
            print(f"Error in category callback: {e}")
            await query.edit_message_text("❌ Error processing category selection.")