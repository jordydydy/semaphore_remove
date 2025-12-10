import re
from app.core.config import settings
from app.adapters.base import BaseAdapter
from app.adapters.utils import split_text_smartly, make_meta_request

class WhatsAppAdapter(BaseAdapter):
    def __init__(self):
        self.version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.version}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        self.token = settings.WHATSAPP_ACCESS_TOKEN

    def _convert_markdown(self, text: str) -> str:
        text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
        text = re.sub(r'~~(.*?)~~', r'~\1~', text)
        return text

    def send_message(self, recipient_id: str, text: str, **kwargs):
        if not self.token: return {"success": False, "error": "No token"}

        text = self._convert_markdown(text)
        chunks = split_text_smartly(text, 4096)
        results = []

        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient_id,
                "type": "text",
                "text": {"body": chunk}
            }
            # Support reply context jika ada
            if kwargs.get("message_id"):
                payload["context"] = {"message_id": kwargs["message_id"]}

            res = make_meta_request("POST", self.base_url, self.token, payload)
            results.append(res)
        
        return {"sent": True, "results": results}

    def send_typing_on(self, recipient_id: str, message_id: str = None):
        """
        Menggabungkan 'mark as read' dan 'typing indicator' dalam satu request.
        """
        if not self.token: return
        
        # Jika ada message_id, kita bisa mark as read sekaligus typing
        if message_id:
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
                "typing_indicator": {
                    "type": "text"
                }
            }
        else:
            # Fallback (jarang terjadi di flow normal): Typing biasa tanpa read status
            # Perhatikan: Endpoint messages biasa untuk typing butuh payload berbeda
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient_id,
                "type": "typing_indicator",
                "typing_indicator": {
                    "type": "typing_on"
                }
            }

        make_meta_request("POST", self.base_url, self.token, payload)

    def send_typing_off(self, recipient_id: str):
        pass

    def mark_as_read(self, message_id: str):
        # Fungsi ini mungkin redundant jika send_typing_on sudah handle read,
        # tapi tetap disimpan untuk keperluan lain.
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        make_meta_request("POST", self.base_url, self.token, payload)

    def send_feedback_request(self, recipient_id: str, answer_id: int):
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Apakah jawaban ini membantu?"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"feedback_good-{answer_id}", "title": "Ya"}},
                        {"type": "reply", "reply": {"id": f"feedback_bad-{answer_id}", "title": "Tidak"}}
                    ]
                }
            }
        }
        return make_meta_request("POST", self.base_url, self.token, payload)