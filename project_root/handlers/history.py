from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler
from utils.database import User, Message, init_db
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

# States
HISTORY_MENU, CONFIRM_CLEAR = range(2)

logger = logging.getLogger(__name__)
Session = init_db()

class HistoryHandler:
    async def get_user_history(self, user_id: int, limit: int = 10) -> list:
        """Get user's message history"""
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return []
            
            messages = session.query(Message)\
                .filter_by(user_id=user.id)\
                .order_by(Message.timestamp.desc())\
                .limit(limit)\
                .all()
            
            return messages

    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show message history"""
        messages = await self.get_user_history(update.effective_user.id)
        
        if not messages:
            await update.message.reply_text("📭 История сообщений пуста")
            return
        
        history_text = "📋 Ваши последние сообщения:\n\n"
        for msg in messages:
            date = msg.timestamp.strftime("%d.%m.%Y %H:%M")
            prefix = "❓" if msg.role == 'user' else "💡"
            history_text += f"🕒 {date}\n{prefix} {msg.content}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="close_history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(history_text, reply_markup=reply_markup)
        return HISTORY_MENU

    async def confirm_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show clear history confirmation"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Да", callback_data="confirm_clear_yes"),
                InlineKeyboardButton("❌ Нет", callback_data="confirm_clear_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите очистить всю историю сообщений?\n"
            "Это действие нельзя отменить!",
            reply_markup=reply_markup
        )
        return CONFIRM_CLEAR

    async def clear_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear user's message history"""
        query = update.callback_query
        await query.answer()
        
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
            if user:
                session.query(Message).filter_by(user_id=user.id).delete()
                session.commit()
        
        await query.edit_message_text("✅ История сообщений очищена")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the conversation"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("❌ Операция отменена")
        return ConversationHandler.END

    def get_conversation_handler(self):
        """Return conversation handler for history management"""
        return ConversationHandler(
            entry_points=[CommandHandler('history', self.show_history)],
            states={
                HISTORY_MENU: [
                    CallbackQueryHandler(self.confirm_clear, pattern="^clear_history$"),
                    CallbackQueryHandler(self.cancel, pattern="^close_history$"),
                ],
                CONFIRM_CLEAR: [
                    CallbackQueryHandler(self.clear_history, pattern="^confirm_clear_yes$"),
                    CallbackQueryHandler(self.cancel, pattern="^confirm_clear_no$"),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.cancel, pattern="^cancel$")],
            allow_reentry=True,
            name="history_conversation",
            persistent=True,
            per_chat=True,
            per_user=True,
            per_message=False,
            conversation_timeout=300  # 5 minutes timeout
        )

    async def save_message(self, user_id: int, content: str, role: str = 'user'):
        """Save message to history"""
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = User(telegram_id=user_id)
                session.add(user)
                session.commit()
            
            message = Message(user_id=user.id, content=content, role=role)
            session.add(message)
            session.commit() 