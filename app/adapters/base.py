from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseAdapter(ABC):
    @abstractmethod
    def send_message(self, recipient_id: str, text: str, **kwargs) -> Dict[str, Any]:
        """Mengirim pesan teks ke user."""
        pass

    @abstractmethod
    def send_typing_on(self, recipient_id: str, message_id: Optional[str] = None):
        """Menyalakan indikator mengetik."""
        pass

    @abstractmethod
    def send_typing_off(self, recipient_id: str):
        """Mematikan indikator mengetik."""
        pass
    
    def send_feedback_request(self, recipient_id: str, answer_id: int) -> Dict[str, Any]:
        """Opsional: Mengirim tombol feedback (Yes/No)."""
        return {"sent": False, "reason": "Not implemented"}