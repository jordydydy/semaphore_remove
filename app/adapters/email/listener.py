import imaplib
import email
import time
import asyncio
import logging
import msal
import requests
from email.header import decode_header
from typing import Dict, Any, Optional

from app.core.config import settings
from app.adapters.email.utils import sanitize_email_body
from app.repositories.message import MessageRepository
from app.api.dependencies import get_orchestrator
from app.schemas.models import IncomingMessage

logger = logging.getLogger("email.listener")
repo = MessageRepository()
_token_cache: Dict[str, Any] = {}

def get_graph_token() -> Optional[str]:
    global _token_cache
    if _token_cache and _token_cache.get("expires_at", 0) > time.time() + 60:
        return _token_cache.get("access_token")
    if not all([settings.AZURE_CLIENT_ID, settings.AZURE_CLIENT_SECRET, settings.AZURE_TENANT_ID]):
        return None
    try:
        app = msal.ConfidentialClientApplication(
            settings.AZURE_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}",
            client_credential=settings.AZURE_CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            _token_cache = {
                "access_token": result["access_token"],
                "expires_at": time.time() + result.get("expires_in", 3500)
            }
            return result["access_token"]
        return None
    except Exception: return None

def _mark_graph_read(user_id, message_id, token):
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/{message_id}"
    try:
        requests.patch(url, json={"isRead": True}, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=5)
    except Exception: pass

def _process_graph_message(user_id, msg, token):
    graph_id = msg.get("id")
    azure_conv_id = msg.get("conversationId") 
    
    if not graph_id: return

    if repo.is_processed(graph_id, "email"):
        logger.warning(f"DUPLIKASI DITOLAK: {graph_id}. Menandai sebagai Read.")
        _mark_graph_read(user_id, graph_id, token)
        return

    clean_body = _extract_graph_body(msg)
    sender_info = msg.get("from", {}).get("emailAddress", {})
    
    metadata = {
        "subject": msg.get("subject", "No Subject"),
        "sender_name": sender_info.get("name", ""),
        "graph_message_id": graph_id,
        "conversation_id": azure_conv_id 
    }

    process_single_email(sender_info.get("address", ""), clean_body, metadata)
    
    _mark_graph_read(user_id, graph_id, token)

def _extract_graph_body(msg):
    body_content = msg.get("body", {}).get("content", "")
    body_type = msg.get("body", {}).get("contentType", "Text")
    return sanitize_email_body(None, body_content) if body_type.lower() == "html" else sanitize_email_body(body_content, None)

def process_single_email(sender_email, body, metadata: dict):
    if "mailer-daemon" in sender_email.lower() or "noreply" in sender_email.lower(): return

    msg = IncomingMessage(
        platform_unique_id=sender_email,
        query=body,
        platform="email",
        metadata=metadata
    )
    
    try:
        orchestrator = get_orchestrator()
        try: loop = asyncio.get_event_loop()
        except RuntimeError: 
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(orchestrator.process_message(msg))
        logger.info(f"Email processed: {sender_email}")
    except Exception as err:
        logger.error(f"Internal Process Error: {err}")

def _poll_graph_api():
    token = get_graph_token()
    if not token: return
    user_id = settings.AZURE_EMAIL_USER
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailFolders/inbox/messages"
    params = {"$filter": "isRead eq false", "$top": 10}
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
        if resp.status_code == 200:
            for msg in resp.json().get("value", []):
                _process_graph_message(user_id, msg, token)
    except Exception as e:
        logger.error(f"Graph Polling Error: {e}")

def start_email_listener():
    if not settings.EMAIL_USER and not settings.AZURE_CLIENT_ID: return
    logger.info(f"Starting Email Listener...")
    while True:
        try:
            if settings.EMAIL_PROVIDER == "azure_oauth2": _poll_graph_api()
            else: pass 
        except Exception: pass
        time.sleep(settings.EMAIL_POLL_INTERVAL_SECONDS)