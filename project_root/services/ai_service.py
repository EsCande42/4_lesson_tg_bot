import os
import asyncio
from openai import AsyncOpenAI
import google.generativeai as genai
from typing import Optional, Dict, Any, AsyncGenerator
import aiohttp
from io import BytesIO
from PIL import Image
import logging

logger = logging.getLogger(__name__)

# Mapping for user-facing names to actual model names
MODEL_MAPPING = {
    "nano-banana": "gemini-1.5-flash-latest"
}

class AIService:
    def __init__(self, openai_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None):
        if not openai_api_key and not gemini_api_key:
            raise ValueError("At least one API key (OpenAI or Gemini) is required.")

        self.openai_client = None
        if openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)

        self.gemini_model = None
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            # We initialize the model here. We can make this more dynamic if needed.
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')


    async def _update_openai_client_base_url(self, base_url: Optional[str]):
        """Dynamically update the base_url for the OpenAI client if provided."""
        if not self.openai_client:
            return
        if base_url:
            self.openai_client.base_url = base_url
        else:
            self.openai_client.base_url = "https://api.openai.com/v1"

    async def _generate_with_gemini(self, messages: list) -> AsyncGenerator[str, None]:
        if not self.gemini_model:
            yield "Gemini client is not configured. Please add GEMINI_API_KEY."
            return

        # Gemini uses a different message format, so we might need to adapt it.
        # For now, assuming a simple conversion.
        gemini_messages = [m['content'] for m in messages if m['role'] == 'user']
        prompt = "\n".join(gemini_messages)

        response = await self.gemini_model.generate_content_async(prompt, stream=True)
        async for chunk in response:
            yield chunk.text

    async def _generate_with_openai(self, settings: Dict[str, Any], messages: list) -> AsyncGenerator[str, None]:
        if not self.openai_client:
            yield "OpenAI client is not configured. Please add OPENAI_API_KEY."
            return

        await self._update_openai_client_base_url(settings.get('base_url'))

        stream = await self.openai_client.chat.completions.create(
            model=settings.get('model', 'gpt-3.5-turbo'),
            messages=messages,
            temperature=settings.get('temperature', 0.7),
            max_tokens=settings.get('max_tokens', 1000),
            stream=True
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def generate_text_stream(
        self,
        settings: Dict[str, Any],
        messages: list
    ) -> AsyncGenerator[str, None]:
        """
        Generates a text response from an AI model using streaming,
        routing to the correct provider based on the selected model.
        """
        model_name = settings.get('model')

        if model_name in MODEL_MAPPING:
            # Route to Gemini
            async for chunk in self._generate_with_gemini(messages):
                yield chunk
        else:
            # Default to OpenAI
            async for chunk in self._generate_with_openai(settings, messages):
                yield chunk

    async def generate_image(self, settings: Dict[str, Any], prompt: str) -> Optional[str]:
        """
        Generates an image based on a prompt and returns the URL.
        """
        if not self.openai_client:
            raise ValueError("OpenAI client is required for image generation.")

        await self._update_openai_client_base_url(settings.get('base_url'))

        image_params = {
            "model": settings.get('model', 'dall-e-3'),
            "prompt": prompt,
            "size": settings.get('size', '1024x1024'),
            "quality": settings.get('quality', 'standard'),
            "style": settings.get('style', 'vivid'),
            "n": 1
        }
        if settings.get('hdr', False):
            image_params["response_format"] = 'url'

        response = await self.openai_client.images.generate(**image_params)
        if response.data:
            return response.data[0].url
        return None

    async def create_image_variation(self, settings: Dict[str, Any], image_data: bytes) -> Optional[str]:
        """
        Creates a variation of an image and returns the URL.
        """
        if not self.openai_client:
            raise ValueError("OpenAI client is required for image variations.")

        await self._update_openai_client_base_url(settings.get('base_url'))

        with Image.open(BytesIO(image_data)) as img:
            if img.size[0] > 1024 or img.size[1] > 1024:
                img.thumbnail((1024, 1024))
            output = BytesIO()
            img.save(output, format='PNG', optimize=True)
            output.seek(0)
            output.name = 'image.png'

        response = await self.openai_client.images.create_variation(
            image=output,
            model=settings.get('model', 'dall-e-2'),
            n=1,
            size=settings.get('size', '1024x1024')
        )
        if response.data:
            return response.data[0].url
        return None

    async def download_image(self, url: str) -> Optional[bytes]:
        """Downloads an image from a URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    logger.error(f"Failed to download image from {url}, status: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e}")
            return None