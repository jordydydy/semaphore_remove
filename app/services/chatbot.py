import httpx
import asyncio
from datetime import datetime, timezone
from app.core.config import settings
from app.schemas.models import ChatbotResponse
import logging

logger = logging.getLogger("service.chatbot")

class ChatbotClient:

    async def _fire_request(self, url: str, payload: dict, headers: dict):
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                await client.post(url, json=payload, headers=headers)
        except Exception as e:
            logger.error(f"Background request failed: {e}")

    async def ask(self, query: str, conversation_id: str, platform: str, user_id: str) -> bool:
        start_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        safe_conv_id = conversation_id or ""

        payload = {
            "query": query,
            "platform": platform,
            "platform_unique_id": user_id,
            "conversation_id": safe_conv_id,
            "start_timestamp": start_timestamp 
        }
        
        headers = {"Content-Type": "application/json"}
        if settings.BACKEND_API_KEY:
            headers["X-API-Key"] = settings.BACKEND_API_KEY

        url = settings.BACKEND_ASK_URL
        
        logger.info(f"PUSH TO BACKEND: {url} | ConvID: {safe_conv_id}")
        
        try:
            asyncio.create_task(self._fire_request(url, payload, headers))
            
            return True

        except Exception as e:
            logger.error(f"Failed to create background task: {e}")
            return False