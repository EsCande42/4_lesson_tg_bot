from telegram import Update
from telegram.ext import ContextTypes
from utils.database import User, UserSettings, init_db, ImageSettings
from sqlalchemy.orm import Session
import logging
from openai import AsyncOpenAI
import asyncio
import os
from typing import Optional
import aiohttp
from io import BytesIO
from utils.logging_config import setup_logging, log_function_call
from PIL import Image
import io

# Initialize logging with just the filename
logger = setup_logging(__name__, 'chat.log')

Session = init_db()

class ChatHandler:
    def __init__(self, history_handler):
        logger.debug("Initializing ChatHandler")
        self.openai_client = AsyncOpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.history_handler = history_handler  # Store the history handler

    async def get_user_settings(self, user_id: int) -> dict:
        """Get user settings"""
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                # Create user if doesn't exist
                user = User(telegram_id=user_id)
                session.add(user)
                session.commit()
            
            settings = session.query(UserSettings).filter_by(user_id=user.id).first()
            if not settings:
                # Create default settings if don't exist
                settings = UserSettings(
                    user_id=user.id,
                    base_url="https://api.openai.com/v1",
                    model="gpt-3.5-turbo",
                    temperature=0.7,
                    max_tokens=1000,
                    use_assistant=False
                )
                session.add(settings)
                session.commit()
                session.refresh(settings)
            
            return {
                'base_url': settings.base_url,
                'model': settings.model,
                'temperature': settings.temperature,
                'max_tokens': settings.max_tokens,
                'use_assistant': settings.use_assistant,
                'assistant_url': settings.assistant_url
            }

    async def get_image_settings(self, user_id: int) -> Optional[ImageSettings]:
        """Get user's image settings"""
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user or not user.image_settings:
                return None
            return user.image_settings

    @log_function_call(logger)
    async def stream_openai_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle streaming chat response"""
        # Get the processed text from context
        message_text = context.user_data.get('processed_text', update.message.text)
        
        # Initial response message
        response_message = await update.message.reply_text(
            "⌛ Генерирую ответ...",
            reply_to_message_id=update.message.message_id
        )
        collected_chunks = []
        last_message = ""
        error_message = "❌ Произошла ошибка при генерации ответа"  # Define error message
        
        try:
            # Get user settings (will create default settings if none exist)
            settings = await self.get_user_settings(update.effective_user.id)
            
            # Configure OpenAI client with user settings
            self.openai_client.base_url = settings['base_url']
            
            if settings['use_assistant'] and settings['assistant_url']:
                # TODO: Implement custom assistant API call
                await response_message.edit_text("🤖 Режим ассистента пока не реализован")
                return
            
            # Start streaming response using processed text
            stream = await self.openai_client.chat.completions.create(
                model=settings['model'],
                messages=[{"role": "user", "content": message_text}],
                temperature=settings['temperature'],
                max_tokens=settings['max_tokens'],
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    collected_chunks.append(chunk.choices[0].delta.content)
                    # Update message every 20 chunks or when chunk ends with sentence
                    if len(collected_chunks) % 20 == 0 or chunk.choices[0].delta.content.endswith(('.', '!', '?')):
                        current_response = ''.join(collected_chunks)
                        if current_response != last_message:  # Only update if content changed
                            try:
                                await response_message.edit_text(current_response)
                                last_message = current_response
                            except Exception as e:
                                if "Message is not modified" not in str(e):
                                    logger.error(f"Error updating message: {e}")
                                continue
                                
            # Final update with complete response
            final_response = ''.join(collected_chunks)
            if final_response != last_message:
                try:
                    await response_message.edit_text(final_response)
                    # Save bot's response to history
                    await self.history_handler.save_message(
                        update.effective_user.id,
                        final_response,
                        role='assistant'
                    )
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        logger.error(f"Error in final update: {e}")
                        await response_message.edit_text(error_message)
            
        except Exception as e:
            error_message = f"❌ Произошла ошибка: {str(e)}"
            logger.error(error_message)
            await response_message.edit_text(error_message)

    async def handle_image_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle image generation request"""
        # Initial response message
        response_message = await update.message.reply_text("🎨 Генерирую изображение...")
        
        try:
            # Get user settings
            settings = await self.get_image_settings(update.effective_user.id)
            if not settings:
                await response_message.edit_text(
                    "⚠️ Пожалуйста, настройте параметры генерации изображений через /image_settings"
                )
                return

            # Get prompt from context
            prompt = context.user_data.get('image_prompt', '')
            if not prompt:
                await response_message.edit_text("❌ Не указан текст для генерации изображения")
                return

            # Configure OpenAI client with user settings
            self.openai_client.base_url = settings.base_url
            
            # Prepare image generation parameters
            image_params = {
                "model": settings.model,
                "prompt": prompt,  # Use prompt from context
                "size": settings.size,
                "quality": settings.quality,
                "style": settings.style,
                "n": 1  # Generate one image
            }
            
            # Add HDR if enabled
            if settings.hdr:
                image_params["hdr"] = True
            
            # Generate image
            response = await self.openai_client.images.generate(**image_params)
            
            if not response.data:
                await response_message.edit_text("❌ Не удалось сгенерировать изображение")
                return
                
            image_url = response.data[0].url
            
            # Download and send the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        await response_message.edit_text("❌ Не удалось загрузить изображение")
                        return
                    
                    image_data = await resp.read()
                    
            # Delete the "generating" message
            await response_message.delete()
            
            # Send the image with the original prompt as caption
            await update.message.reply_photo(
                photo=BytesIO(image_data),
                caption=f"🎨 Prompt: {prompt}"
            )
            
            # Clean up context
            if 'image_prompt' in context.user_data:
                del context.user_data['image_prompt']
            
        except Exception as e:
            error_message = f"❌ Произошла ошибка при генерации изображения: {str(e)}"
            logger.error(error_message)
            await response_message.edit_text(error_message)

    async def handle_image_variation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle image variation generation"""
        if not update.message.photo:
            await update.message.reply_text(
                "⚠️ Пожалуйста, отправьте изображение для создания вариации"
            )
            return
            
        response_message = await update.message.reply_text("🎨 Создаю вариацию изображения...")
        
        try:
            # Get user settings
            settings = await self.get_image_settings(update.effective_user.id)
            if not settings:
                await response_message.edit_text(
                    "⚠️ Пожалуйста, настройте параметры генерации изображений через /image_settings"
                )
                return

            # Get the largest photo version
            photo = update.message.photo[-1]
            
            # Check file size
            if photo.file_size > 4 * 1024 * 1024:  # 4 MB in bytes
                await response_message.edit_text("❌ Размер изображения должен быть меньше 4 МБ")
                return
            
            # Download the photo
            photo_file = await context.bot.get_file(photo.file_id)
            
            # Create a BytesIO object for the image
            import io
            
            # Download image data
            photo_data = await photo_file.download_as_bytearray()
            image = Image.open(io.BytesIO(photo_data))
            
            # Convert to PNG and optimize
            output = io.BytesIO()
            image.save(output, format='PNG', optimize=True)
            output.seek(0)
            output.name = 'image.png'
            
            # Generate variation
            response = await self.openai_client.images.create_variation(
                image=output,
                model=settings.model,
                n=1,
                size=settings.size
            )
            
            if not response.data:
                await response_message.edit_text("❌ Не удалось создать вариацию изображения")
                return
                
            variation_url = response.data[0].url
            
            # Download and send the variation
            async with aiohttp.ClientSession() as session:
                async with session.get(variation_url) as resp:
                    if resp.status != 200:
                        await response_message.edit_text("❌ Не удалось загрузить вариацию")
                        return
                    
                    variation_data = await resp.read()
                    
            # Delete the "generating" message
            await response_message.delete()
            
            # Send the variation
            await update.message.reply_photo(
                photo=BytesIO(variation_data),
                caption="🎨 Вариация изображения"
            )
            
        except Exception as e:
            error_message = f"❌ Произошла ошибка при создании вариации: {str(e)}"
            logger.error(error_message)
            await response_message.edit_text(error_message)