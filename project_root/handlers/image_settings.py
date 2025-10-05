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
from typing import Any

logger = logging.getLogger(__name__)

# Conversation states
(
    IMAGE_MAIN_MENU,
    IMAGE_MODEL_SELECTION,
    IMAGE_SIZE_SELECTION,
    IMAGE_QUALITY_SELECTION,
    IMAGE_STYLE_SELECTION,
    IMAGE_BASE_URL_INPUT,
) = range(6)


class ImageSettingsHandler:
    def __init__(self):
        self.db_service = database_service
        self.menus = {
            "model": {
                "dall-e-3": "DALL-E 3",
                "dall-e-2": "DALL-E 2",
            },
            "size": {
                "1024x1024": "Квадрат (1024x1024)",
                "1792x1024": "Широкий (1792x1024)",
                "1024x1792": "Высокий (1024x1792)",
            },
            "quality": {"standard": "Стандарт", "hd": "HD"},
            "style": {"natural": "Натуральный", "vivid": "Яркий"},
        }

    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Displays the main image settings menu."""
        user_id = update.effective_user.id
        settings = await self.db_service.get_image_settings(user_id)

        text = (
            "🖼 Настройки генерации изображений:\n\n"
            f"🌐 URL: `{settings['base_url']}`\n"
            f"🎨 Модель: `{settings['model']}`\n"
            f"📐 Размер: `{settings['size']}`\n"
            f"✨ Качество: `{settings['quality']}`\n"
            f"🎭 Стиль: `{settings['style']}`"
        )
        keyboard = [
            [InlineKeyboardButton("📝 Изменить URL", callback_data="img_edit_base_url")],
            [InlineKeyboardButton("🎨 Выбрать модель", callback_data="img_select_model")],
            [InlineKeyboardButton("📐 Выбрать размер", callback_data="img_select_size")],
            [InlineKeyboardButton("✨ Выбрать качество", callback_data="img_select_quality")],
            [InlineKeyboardButton("🎭 Выбрать стиль", callback_data="img_select_style")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="img_close")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

        return IMAGE_MAIN_MENU

    async def _selection_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, setting_key: str, state: int) -> int:
        """Generic method to show a selection menu."""
        query = update.callback_query
        await query.answer()

        options = self.menus[setting_key]
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"img_set_{setting_key}_{key}")]
            for key, name in options.items()
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="img_back_to_menu")])
        
        await query.edit_message_text(f"Выберите {setting_key}:", reply_markup=InlineKeyboardMarkup(keyboard))
        return state

    async def _update_setting(self, user_id: int, key: str, value: Any) -> None:
        """Helper to update a specific image setting."""
        await self.db_service.update_image_settings(user_id, {key: value})

    async def handle_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handles a selection from any of the menus."""
        query = update.callback_query
        _, _, key, value = query.data.split("_", 3)
        
        await self._update_setting(query.from_user.id, key, value)
        await query.answer(f"Настройка '{key}' обновлена.")
        return await self.main_menu(update, context)

    async def request_base_url_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Введите новый Base URL для изображений:")
        return IMAGE_BASE_URL_INPUT

    async def handle_base_url_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        url = update.message.text
        await self._update_setting(user_id, "base_url", url)
        await update.message.reply_text("✅ Base URL для изображений обновлен.")
        return await self.main_menu(update, context)

    async def close_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.message.delete()
        return ConversationHandler.END

    def get_conversation_handler(self) -> ConversationHandler:
        """Creates and returns the image settings ConversationHandler."""
        return ConversationHandler(
            entry_points=[CommandHandler("image_settings", self.main_menu)],
            states={
                IMAGE_MAIN_MENU: [
                    CallbackQueryHandler(self.request_base_url_input, pattern="^img_edit_base_url$"),
                    CallbackQueryHandler(lambda u, c: self._selection_menu(u, c, "model", IMAGE_MODEL_SELECTION), pattern="^img_select_model$"),
                    CallbackQueryHandler(lambda u, c: self._selection_menu(u, c, "size", IMAGE_SIZE_SELECTION), pattern="^img_select_size$"),
                    CallbackQueryHandler(lambda u, c: self._selection_menu(u, c, "quality", IMAGE_QUALITY_SELECTION), pattern="^img_select_quality$"),
                    CallbackQueryHandler(lambda u, c: self._selection_menu(u, c, "style", IMAGE_STYLE_SELECTION), pattern="^img_select_style$"),
                    CallbackQueryHandler(self.close_menu, pattern="^img_close$"),
                ],
                IMAGE_MODEL_SELECTION: [CallbackQueryHandler(self.handle_selection, pattern="^img_set_model_")],
                IMAGE_SIZE_SELECTION: [CallbackQueryHandler(self.handle_selection, pattern="^img_set_size_")],
                IMAGE_QUALITY_SELECTION: [CallbackQueryHandler(self.handle_selection, pattern="^img_set_quality_")],
                IMAGE_STYLE_SELECTION: [CallbackQueryHandler(self.handle_selection, pattern="^img_set_style_")],
                IMAGE_BASE_URL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_base_url_input)],
            },
            fallbacks=[
                CallbackQueryHandler(self.main_menu, pattern="^img_back_to_menu$"),
                CommandHandler("cancel", self.close_menu)
            ],
            name="image_settings_conversation",
            persistent=True,
        )