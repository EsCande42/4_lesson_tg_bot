from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from utils.database import User, ImageSettings, init_db
from sqlalchemy.orm import Session
import logging
import telegram.error

# States for image settings conversation
(IMAGE_MAIN_MENU, IMAGE_BASE_URL, IMAGE_MODEL, 
 IMAGE_SIZE, IMAGE_QUALITY, IMAGE_STYLE) = range(6)

logger = logging.getLogger(__name__)
Session = init_db()

class ImageSettingsHandler:
    def __init__(self):
        self.available_models = {
            "dall-e-3": "DALL-E 3",
            "dall-e-2": "DALL-E 2",
            "stable-diffusion-xl": "Stable Diffusion XL",
            "midjourney": "Midjourney API"
        }
        
        self.size_options = {
            "1024x1024": "1024x1024 (Квадрат)",
            "1792x1024": "1792x1024 (Широкий)",
            "1024x1792": "1024x1792 (Высокий)",
        }
        
        self.quality_options = {
            "standard": "Стандартное",
            "hd": "Высокое (HD)"
        }
        
        self.style_options = {
            "natural": "Натуральный",
            "vivid": "Яркий",
            "anime": "Аниме"
        }

    async def get_or_create_settings(self, user_id: int) -> dict:
        """Get or create image settings"""
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = User(telegram_id=user_id)
                session.add(user)
                session.commit()
            
            settings = session.query(ImageSettings).filter_by(user_id=user.id).first()
            if not settings:
                settings = ImageSettings(
                    user_id=user.id,
                    base_url="https://api.openai.com/v1",
                    model="dall-e-3",
                    size="1024x1024",
                    quality="standard",
                    style="natural",
                    hdr=False
                )
                session.add(settings)
                session.commit()
                session.refresh(settings)
            
            return {
                'base_url': settings.base_url,
                'model': settings.model,
                'size': settings.size,
                'quality': settings.quality,
                'style': settings.style,
                'hdr': settings.hdr
            }

    async def image_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main image settings menu"""
        # Get user_id correctly depending on update type
        if isinstance(update, Update):
            if update.callback_query:
                user_id = update.callback_query.from_user.id
            else:
                user_id = update.effective_user.id
        else:
            user_id = update.from_user.id

        keyboard = [
            [InlineKeyboardButton("🌐 Базовый URL", callback_data="edit_image_base_url")],
            [InlineKeyboardButton("🎨 Модель", callback_data="select_image_model")],
            [InlineKeyboardButton("📐 Размер", callback_data="select_image_size")],
            [InlineKeyboardButton("✨ Качество", callback_data="select_image_quality")],
            [InlineKeyboardButton("🎭 Стиль", callback_data="select_image_style")],
            [InlineKeyboardButton("HDR", callback_data="toggle_hdr")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="close_image_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        settings = await self.get_or_create_settings(user_id)
        text = (
            "🖼 Настройки генерации изображений:\n\n"
            f"🌐 URL: {settings['base_url']}\n"
            f"🎨 Модель: {settings['model']}\n"
            f"📐 Размер: {settings['size']}\n"
            f"✨ Качество: {settings['quality']}\n"
            f"🎭 Стиль: {settings['style']}\n"
            f"HDR: {'Вкл' if settings['hdr'] else 'Выкл'}"
        )
        
        try:
            if isinstance(update, Update) and update.callback_query:
                try:
                    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
                except telegram.error.BadRequest as e:
                    if "Message is not modified" not in str(e):
                        raise
            elif isinstance(update, CallbackQuery):
                try:
                    await update.edit_message_text(text=text, reply_markup=reply_markup)
                except telegram.error.BadRequest as e:
                    if "Message is not modified" not in str(e):
                        raise
            else:
                await update.message.reply_text(text=text, reply_markup=reply_markup)
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error in image_settings_menu: {e}", exc_info=True)
                error_message = "❌ Произошла ошибка при отображении настроек. Попробуйте еще раз /image_settings"
                if isinstance(update, (Update, CallbackQuery)) and hasattr(update, 'callback_query'):
                    await update.callback_query.message.reply_text(error_message)
                else:
                    await update.message.reply_text(error_message)
        
        return IMAGE_MAIN_MENU

    async def select_image_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show image model selection menu"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for model_id, model_name in self.available_models.items():
            keyboard.append([InlineKeyboardButton(model_name, callback_data=f"set_model_{model_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_image_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите модель для генерации изображений:", reply_markup=reply_markup)
        return IMAGE_MODEL

    async def select_image_size(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show image size selection menu"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for size_id, size_name in self.size_options.items():
            keyboard.append([InlineKeyboardButton(size_name, callback_data=f"set_size_{size_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_image_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите размер изображения:", reply_markup=reply_markup)
        return IMAGE_SIZE

    async def select_image_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show image quality selection menu"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for quality_id, quality_name in self.quality_options.items():
            keyboard.append([InlineKeyboardButton(quality_name, callback_data=f"set_quality_{quality_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_image_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите качество изображения:", reply_markup=reply_markup)
        return IMAGE_QUALITY

    async def select_image_style(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show image style selection menu"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for style_id, style_name in self.style_options.items():
            keyboard.append([InlineKeyboardButton(style_name, callback_data=f"set_style_{style_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_image_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите стиль изображения:", reply_markup=reply_markup)
        return IMAGE_STYLE

    async def toggle_hdr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle HDR setting"""
        query = update.callback_query
        await query.answer()
        
        try:
            with Session() as session:
                user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
                if not user:
                    user = User(telegram_id=query.from_user.id)
                    session.add(user)
                    session.commit()
                
                settings = session.query(ImageSettings).filter_by(user_id=user.id).first()
                if not settings:
                    settings = ImageSettings(user_id=user.id)
                    session.add(settings)
                
                # Toggle HDR setting
                settings.hdr = not settings.hdr
                session.commit()
                logger.debug(f"Toggled HDR to {settings.hdr} for user {query.from_user.id}")
            
            # Return to the main menu with updated settings
            return await self.image_settings_menu(query, context)
            
        except Exception as e:
            logger.error(f"Error toggling HDR: {e}", exc_info=True)
            await query.message.reply_text("❌ Произошла ошибка при изменении настройки HDR")
            return await self.image_settings_menu(query, context)

    async def handle_setting_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle settings updates"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        setting_type = data.split('_')[1]
        value = '_'.join(data.split('_')[2:])
        
        try:
            with Session() as session:
                user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
                if not user:
                    user = User(telegram_id=query.from_user.id)
                    session.add(user)
                    session.commit()
                
                settings = session.query(ImageSettings).filter_by(user_id=user.id).first()
                if not settings:
                    settings = ImageSettings(user_id=user.id)
                    session.add(settings)
                
                # Update the appropriate setting
                if setting_type == 'model':
                    settings.model = value
                elif setting_type == 'size':
                    settings.size = value
                elif setting_type == 'quality':
                    settings.quality = value
                elif setting_type == 'style':
                    settings.style = value
                
                session.commit()
                logger.debug(f"Updated {setting_type} to {value} for user {query.from_user.id}")
            
            return await self.image_settings_menu(query, context)
        
        except Exception as e:
            logger.error(f"Error updating setting: {e}", exc_info=True)
            await query.message.reply_text("❌ Произошла ошибка при обновлении настроек")
            return await self.image_settings_menu(query, context)

    async def handle_base_url_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start base URL input process"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Введите новый Base URL для модели изображений:")
        return IMAGE_BASE_URL

    async def handle_base_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle base URL input"""
        new_url = update.message.text
        
        try:
            with Session() as session:
                user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
                if not user:
                    user = User(telegram_id=update.effective_user.id)
                    session.add(user)
                    session.commit()
                
                settings = session.query(ImageSettings).filter_by(user_id=user.id).first()
                if not settings:
                    settings = ImageSettings(user_id=user.id)
                    session.add(settings)
                
                settings.base_url = new_url
                session.commit()
                logger.debug(f"Updated base URL to {new_url} for user {update.effective_user.id}")
            
            await update.message.reply_text(f"✅ Base URL обновлен на: {new_url}")
            return await self.image_settings_menu(update, context)
            
        except Exception as e:
            logger.error(f"Error updating base URL: {e}", exc_info=True)
            await update.message.reply_text("❌ Произошла ошибка при обновлении Base URL")
            return await self.image_settings_menu(update, context)

    def get_conversation_handler(self):
        """Return conversation handler for image settings"""
        return ConversationHandler(
            entry_points=[CommandHandler('image_settings', self.image_settings_menu)],
            states={
                IMAGE_MAIN_MENU: [
                    CallbackQueryHandler(self.handle_base_url_start, pattern="^edit_image_base_url$"),
                    CallbackQueryHandler(self.select_image_model, pattern="^select_image_model$"),
                    CallbackQueryHandler(self.select_image_size, pattern="^select_image_size$"),
                    CallbackQueryHandler(self.select_image_quality, pattern="^select_image_quality$"),
                    CallbackQueryHandler(self.select_image_style, pattern="^select_image_style$"),
                    CallbackQueryHandler(self.toggle_hdr, pattern="^toggle_hdr$"),
                    CallbackQueryHandler(self.cancel, pattern="^close_image_settings$"),
                ],
                IMAGE_BASE_URL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_base_url),
                    CallbackQueryHandler(self.image_settings_menu, pattern="^back_to_image_menu$"),
                ],
                IMAGE_MODEL: [
                    CallbackQueryHandler(self.handle_setting_update, pattern="^set_model_"),
                    CallbackQueryHandler(self.image_settings_menu, pattern="^back_to_image_menu$"),
                ],
                IMAGE_SIZE: [
                    CallbackQueryHandler(self.handle_setting_update, pattern="^set_size_"),
                    CallbackQueryHandler(self.image_settings_menu, pattern="^back_to_image_menu$"),
                ],
                IMAGE_QUALITY: [
                    CallbackQueryHandler(self.handle_setting_update, pattern="^set_quality_"),
                    CallbackQueryHandler(self.image_settings_menu, pattern="^back_to_image_menu$"),
                ],
                IMAGE_STYLE: [
                    CallbackQueryHandler(self.handle_setting_update, pattern="^set_style_"),
                    CallbackQueryHandler(self.image_settings_menu, pattern="^back_to_image_menu$"),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.cancel, pattern="^close_image_settings$")],
            allow_reentry=True,
            name="image_settings_conversation",
            persistent=True,
            per_chat=True,
            per_user=True,
            per_message=False,
            conversation_timeout=300  # 5 minutes timeout
        ) 

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel and close settings menu"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Настройки изображений закрыты")
        return ConversationHandler.END