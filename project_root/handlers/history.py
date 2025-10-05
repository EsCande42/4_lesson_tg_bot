from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler
from services.database_service import database_service
import logging

# States for conversation
HISTORY_MENU, CONFIRM_CLEAR = range(2)

logger = logging.getLogger(__name__)

class HistoryHandler:
    def __init__(self):
        self.db_service = database_service

    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Shows the user's message history."""
        user_id = update.effective_user.id
        messages = await self.db_service.get_message_history(user_id, limit=15)
        
        if not messages:
            await update.message.reply_text("📭 История сообщений пуста.")
            return ConversationHandler.END
        
        history_text = "📋 Ваши последние 15 сообщений:\n\n"
        for msg in messages:
            date = msg['timestamp'].strftime("%d.%m.%Y %H:%M")
            prefix = "❓" if msg['role'] == 'user' else "💡"
            history_text += f"🕒 {date}\n{prefix} {msg['content']}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="close_history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(history_text, reply_markup=reply_markup)
        return HISTORY_MENU

    async def confirm_clear_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Asks for confirmation before clearing history."""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear_yes"),
                InlineKeyboardButton("❌ Нет, оставить", callback_data="confirm_clear_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите очистить всю историю сообщений?\n"
            "Это действие необратимо!",
            reply_markup=reply_markup
        )
        return CONFIRM_CLEAR

    async def clear_history_confirmed(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Clears the user's message history after confirmation."""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        await self.db_service.clear_message_history(user_id)
        
        await query.edit_message_text("✅ История сообщений была успешно очищена.")
        return ConversationHandler.END

    async def close_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Closes the history view."""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Меню истории закрыто.")
        return ConversationHandler.END

    async def save_message(self, user_id: int, content: str, role: str = 'user'):
        """Saves a message to the history using the database service."""
        await self.db_service.add_message_to_history(user_id, role, content)

    def get_conversation_handler(self) -> ConversationHandler:
        """Creates and returns the ConversationHandler for history management."""
        return ConversationHandler(
            entry_points=[CommandHandler('history', self.show_history)],
            states={
                HISTORY_MENU: [
                    CallbackQueryHandler(self.confirm_clear_prompt, pattern="^clear_history$"),
                    CallbackQueryHandler(self.close_history, pattern="^close_history$"),
                ],
                CONFIRM_CLEAR: [
                    CallbackQueryHandler(self.clear_history_confirmed, pattern="^confirm_clear_yes$"),
                    CallbackQueryHandler(self.close_history, pattern="^confirm_clear_no$"),
                ],
            },
            fallbacks=[CommandHandler('start', self.close_history)],
            allow_reentry=True,
            name="history_conversation",
            persistent=True,
        )