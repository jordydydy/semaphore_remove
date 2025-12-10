from typing import Optional, List, Tuple
from app.repositories.base import Database
from app.core.exceptions import DatabaseError
import logging

logger = logging.getLogger("repo.conversation")

class ConversationRepository:
    def get_active_id(self, platform_id: str, platform: str) -> Optional[str]:
        try:
            with Database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, end_timestamp
                        FROM bkpm.conversations
                        WHERE platform_unique_id = %s AND platform = %s
                        ORDER BY start_timestamp DESC
                        LIMIT 1
                        """,
                        (platform_id, platform)
                    )
                    row = cursor.fetchone()
                    
                    if row:
                        conversation_id, end_timestamp = row
                        if end_timestamp is None:
                            return str(conversation_id)
            return None
        except Exception as e:
            logger.error(f"Error fetching active conversation: {e}")
            raise DatabaseError("Failed to fetch conversation")

    def get_latest_id(self, platform_id: str, platform: str) -> Optional[str]:
        try:
            with Database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM bkpm.conversations
                        WHERE platform_unique_id = %s AND platform = %s
                        ORDER BY start_timestamp DESC
                        LIMIT 1
                        """,
                        (platform_id, platform)
                    )
                    row = cursor.fetchone()
                    return str(row[0]) if row else None
        except Exception as e:
            logger.error(f"Error fetching latest conversation: {e}")
            return None

    # [UPDATE] Filter Hari Ini & Cek History Chat
    def get_stale_sessions(self, minutes: int = 15) -> List[Tuple[str, str, str]]:
        """
        Mencari sesi WA/IG aktif HARI INI yang pesan terakhirnya sudah 'basi'.
        """
        try:
            with Database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT c.id, c.platform, c.platform_unique_id
                        FROM bkpm.conversations c
                        WHERE c.end_timestamp IS NULL 
                        AND c.platform IN ('whatsapp', 'instagram')
                        -- [FIX] Hanya cek sesi yang dibuat HARI INI (untuk hindari data kotor lama)
                        AND c.start_timestamp >= CURRENT_DATE
                        AND (
                            SELECT MAX(ch.created_at) 
                            FROM bkpm.chat_history ch 
                            WHERE ch.session_id = c.id
                        ) < NOW() - INTERVAL '{minutes} minutes'
                        LIMIT 50
                        """
                    )
                    rows = cursor.fetchall()
                    return [(str(row[0]), row[1], row[2]) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching stale sessions: {e}")
            return []