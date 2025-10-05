import os
import asyncio
from openai import AsyncOpenAI
from typing import Optional, Dict, Any, AsyncGenerator
import aiohttp
from io import BytesIO
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = AsyncOpenAI(api_key=api_key)

    async def _update_client_base_url(self, base_url: Optional[str]):
        """Dynamically update the base_url for the client if provided."""
        if base_url:
            self.client.base_url = base_url
        else:
            # Reset to default if no base_url is provided
            self.client.base_url = "https://api.openai.com/v1"

    async def generate_text_stream(
        self,
        settings: Dict[str, Any],
        messages: list
    ) -> AsyncGenerator[str, None]:
        """
        Generates a text response from OpenAI using streaming.
        """
        await self._update_client_base_url(settings.get('base_url'))

        stream = await self.client.chat.completions.create(
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

    async def generate_image(self, settings: Dict[str, Any], prompt: str) -> Optional[str]:
        """
        Generates an image based on a prompt and returns the URL.
        """
        await self._update_client_base_url(settings.get('base_url'))

        image_params = {
            "model": settings.get('model', 'dall-e-3'),
            "prompt": prompt,
            "size": settings.get('size', '1024x1024'),
            "quality": settings.get('quality', 'standard'),
            "style": settings.get('style', 'vivid'),
            "n": 1
        }
        if settings.get('hdr', False):
            image_params["response_format"] = 'url' # DALL-E 3 specific setting for style/quality

        response = await self.client.images.generate(**image_params)
        if response.data:
            return response.data[0].url
        return None

    async def create_image_variation(self, settings: Dict[str, Any], image_data: bytes) -> Optional[str]:
        """
        Creates a variation of an image and returns the URL.
        """
        await self._update_client_base_url(settings.get('base_url'))

        # Convert image to PNG and optimize
        with Image.open(BytesIO(image_data)) as img:
            if img.size[0] > 1024 or img.size[1] > 1024: # Resize if needed
                img.thumbnail((1024, 1024))

            output = BytesIO()
            img.save(output, format='PNG', optimize=True)
            output.seek(0)
            output.name = 'image.png'

        response = await self.client.images.create_variation(
            image=output,
            model=settings.get('model', 'dall-e-2'), # DALL-E 2 is typically used for variations
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
                    else:
                        logger.error(f"Failed to download image from {url}, status: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e}")
            return None