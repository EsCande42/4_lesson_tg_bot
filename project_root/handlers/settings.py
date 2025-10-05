from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from services.database_service import database_service
import logging

logger = logging.getLogger(__name__)

# Conversation states
(
    MAIN_MENU,
    MODEL_SELECTION,
    BASE_URL,
    CUSTOM_MODEL,
    TEMPERATURE,
    MAX_TOKENS,
    ASSISTANT_URL,
) = range(7)


class SettingsHandler:
    def __init__(self):
        self.db_service = database_service
        self.available_models = {
            "gpt-3.5-turbo": "GPT-3.5 Turbo",
            "gpt-4": "GPT-4",
            "gpt-4-turbo": "GPT-4 Turbo",
            "gpt-4o-mini": "GPT-4o-mini",
        }

    async def settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Displays the main settings menu."""
        user_id = update.effective_user.id
        settings = await self.db_service.get_user_settings(user_id)

        text = (
            "⚙️ Текущие настройки текстовой модели:\n\n"
            f"🌐 URL: `{settings['base_url']}`\n"
            f"🤖 Модель: `{settings['model']}`\n"
            f"🌡️ Температура: `{settings['temperature']}`\n"
            f"📊 Макс. токенов: `{settings['max_tokens']}`\n"
            f"🔗 Ассистент: `{'Включен' if settings['use_assistant'] else 'Выключен'}`"
        )
        keyboard = [
            [InlineKeyboardButton("📝 Изменить URL", callback_data="edit_base_url")],
            [InlineKeyboardButton("🤖 Выбрать модель", callback_data="select_model")],
            [InlineKeyboardButton("🌡️ Изменить температуру", callback_data="edit_temperature")],
            [InlineKeyboardButton("📊 Изменить макс. токенов", callback_data="edit_max_tokens")],
            [InlineKeyboardButton("🔗 Изменить URL ассистента", callback_data="edit_assistant_url")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="close")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

        return MAIN_MENU

    async def model_selection_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Shows the model selection menu."""
        query = update.callback_query
        await query.answer()

        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"model_{key}")]
            for key, name in self.available_models.items()
        ]
        keyboard.append([InlineKeyboardButton("✏️ Указать свою модель", callback_data="custom_model")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])
        
        await query.edit_message_text("Выберите модель:", reply_markup=InlineKeyboardMarkup(keyboard))
        return MODEL_SELECTION

    async def temperature_selection_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Shows the temperature selection menu."""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton(f"🌡️ {i/10.0}", callback_data=f"temp_{i/10.0}")]
            for i in range(0, 11, 2)
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            "Выберите температуру (0 = точно, 1 = креативно):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TEMPERATURE

    async def _update_setting(self, user_id: int, key: str, value: Any) -> None:
        """Helper to update a specific setting."""
        await self.db_service.update_user_settings(user_id, {key: value})

    async def handle_model_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        model = query.data.split("_", 1)[1]
        await self._update_setting(query.from_user.id, "model", model)
        await query.answer(f"Модель изменена на {model}")
        return await self.settings_menu(update, context)

    async def handle_temperature_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        temp = float(query.data.split("_", 1)[1])
        await self._update_setting(query.from_user.id, "temperature", temp)
        await query.answer(f"Температура изменена на {temp}")
        return await self.settings_menu(update, context)

    async def request_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str, state: int) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(message)
        return state

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, key: str) -> int:
        user_id = update.effective_user.id
        value = update.message.text

        if key == "max_tokens":
            try:
                value = int(value)
                if value < 150:
                    await update.message.reply_text("⚠️ Минимальное значение: 150. Попробуйте снова.")
                    return MAX_TOKENS
            except ValueError:
                await update.message.reply_text("⚠️ Введите число. Попробуйте снова.")
                return MAX_TOKENS

        await self._update_setting(user_id, key, value)
        await update.message.reply_text(f"✅ Настройка `{key}` обновлена.")
        return await self.settings_menu(update, context)

    async def close_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Closes the settings menu."""
        query = update.callback_query
        await query.answer()
        await query.message.delete()
        return ConversationHandler.END

    def get_conversation_handler(self) -> ConversationHandler:
        """Creates and returns the settings ConversationHandler."""
        return ConversationHandler(
            entry_points=[CommandHandler("settings", self.settings_menu)],
            states={
                MAIN_MENU: [
                    CallbackQueryHandler(self.model_selection_menu, pattern="^select_model$"),
                    CallbackQueryHandler(self.temperature_selection_menu, pattern="^edit_temperature$"),
                    CallbackQueryHandler(lambda u, c: self.request_input(u, c, "Введите новый Base URL:", BASE_URL), pattern="^edit_base_url$"),
                    CallbackQueryHandler(lambda u, c: self.request_input(u, c, "Введите название своей модели:", CUSTOM_MODEL), pattern="^custom_model$"),
                    CallbackQueryHandler(lambda u, c: self.request_input(u, c, "Введите макс. количество токенов (мин. 150):", MAX_TOKENS), pattern="^edit_max_tokens$"),
                    CallbackQueryHandler(lambda u, c: self.request_input(u, c, "Введите URL ассистента:", ASSISTANT_URL), pattern="^edit_assistant_url$"),
                    CallbackQueryHandler(self.close_menu, pattern="^close$"),
                ],
                MODEL_SELECTION: [
                    CallbackQueryHandler(self.handle_model_selected, pattern="^model_"),
                    CallbackQueryHandler(self.settings_menu, pattern="^back_to_menu$"),
                ],
                TEMPERATURE: [
                    CallbackQueryHandler(self.handle_temperature_selected, pattern="^temp_"),
                    CallbackQueryHandler(self.settings_menu, pattern="^back_to_menu$"),
                ],
                BASE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: self.handle_text_input(u, c, "base_url"))],
                CUSTOM_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: self.handle_text_input(u, c, "model"))],
                MAX_TOKENS: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: self.handle_text_input(u, c, "max_tokens"))],
                ASSISTANT_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: self.handle_text_input(u, c, "assistant_url"))],
            },
            fallbacks=[CommandHandler("cancel", self.close_menu)],
            name="text_settings_conversation",
            persistent=True,
        )