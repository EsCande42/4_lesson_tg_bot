import os
from telegram import Update
from telegram.ext import ContextTypes
from services.database_service import database_service
from services.ai_service import AIService
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

class ChatHandler:
    def __init__(self):
        logger.debug("Initializing ChatHandler with AI service")
        self.db_service = database_service
        self.ai_service = AIService(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            gemini_api_key=os.getenv('GEMINI_API_KEY')
        )

    async def stream_ai_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles streaming chat response using the new service layer."""
        message_text = context.user_data.get('processed_text', update.message.text)
        user_id = update.effective_user.id

        response_message = await update.message.reply_text(
            "⌛ Генерирую ответ...",
            reply_to_message_id=update.message.message_id
        )

        try:
            # 1. Get user settings from the database service
            settings = await self.db_service.get_user_settings(user_id)
            
            # TODO: Implement custom assistant logic if needed
            if settings.get('use_assistant') and settings.get('assistant_url'):
                await response_message.edit_text("🤖 Режим ассистента пока не реализован")
                return

            # 2. Get message history
            history = await self.db_service.get_message_history(user_id)
            messages = history + [{"role": "user", "content": message_text}]

            # 3. Stream response from OpenAI service
            full_response = ""
            last_edit_text = ""
            
            async for chunk in self.ai_service.generate_text_stream(settings, messages):
                full_response += chunk
                # Edit message only when the text changes significantly to avoid rate limits
                if len(full_response) > len(last_edit_text) + 20 and ('\n' in full_response or '.' in full_response):
                    try:
                        await response_message.edit_text(full_response + "...")
                        last_edit_text = full_response
                    except Exception as e:
                        if "Message is not modified" not in str(e):
                            logger.warning(f"Could not edit message: {e}")

            # 4. Final update and save to history
            await response_message.edit_text(full_response)
            await self.db_service.add_message_to_history(user_id, 'assistant', full_response)

        except Exception as e:
            error_message = f"❌ Произошла ошибка: {e}"
            logger.error(error_message, exc_info=True)
            await response_message.edit_text(error_message)

    async def handle_image_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles image generation using the new service layer."""
        user_id = update.effective_user.id
        prompt = context.user_data.get('image_prompt', '')

        if not prompt:
            await update.message.reply_text("❌ Не указан текст для генерации изображения.")
            return

        response_message = await update.message.reply_text("🎨 Генерирую изображение...")

        try:
            # 1. Get image settings
            settings = await self.db_service.get_image_settings(user_id)

            # 2. Generate image URL via AI service
            image_url = await self.ai_service.generate_image(settings, prompt)
            if not image_url:
                await response_message.edit_text("❌ Не удалось сгенерировать изображение.")
                return
            
            # 3. Download image data
            image_data = await self.ai_service.download_image(image_url)
            if not image_data:
                await response_message.edit_text("❌ Не удалось загрузить сгенерированное изображение.")
                return

            # 4. Send photo
            await response_message.delete()
            await update.message.reply_photo(photo=BytesIO(image_data), caption=f"🎨 Prompt: {prompt}")

        except Exception as e:
            error_message = f"❌ Произошла ошибка при генерации изображения: {e}"
            logger.error(error_message, exc_info=True)
            await response_message.edit_text(error_message)
        finally:
            if 'image_prompt' in context.user_data:
                del context.user_data['image_prompt']

    async def handle_image_variation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles image variation using the new service layer."""
        user_id = update.effective_user.id
        if not update.message.photo:
            await update.message.reply_text("⚠️ Пожалуйста, отправьте изображение для создания вариации.")
            return

        response_message = await update.message.reply_text("🎨 Создаю вариацию изображения...")
        
        try:
            photo = update.message.photo[-1]
            if photo.file_size > 4 * 1024 * 1024:
                await response_message.edit_text("❌ Размер файла не должен превышать 4 МБ.")
                return

            # 1. Get image settings
            settings = await self.db_service.get_image_settings(user_id)

            # 2. Download user's image
            photo_file = await context.bot.get_file(photo.file_id)
            image_data = await photo_file.download_as_bytearray()

            # 3. Create variation URL via AI service
            variation_url = await self.ai_service.create_image_variation(settings, bytes(image_data))
            if not variation_url:
                await response_message.edit_text("❌ Не удалось создать вариацию.")
                return
            
            # 4. Download the new image
            variation_data = await self.ai_service.download_image(variation_url)
            if not variation_data:
                await response_message.edit_text("❌ Не удалось загрузить вариацию изображения.")
                return

            # 5. Send photo
            await response_message.delete()
            await update.message.reply_photo(photo=BytesIO(variation_data), caption="🎨 Вариация изображения")

        except Exception as e:
            error_message = f"❌ Произошла ошибка при создании вариации: {e}"
            logger.error(error_message, exc_info=True)
            await response_message.edit_text(error_message)