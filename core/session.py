import os
import json
import time
import asyncio
from typing import Optional
from config import SESSION_TTL, SESSION_DIR, logger


class Session:
    def __init__(self, conversation_id: str, user_token: str, user_info: dict = None):
        self.conversation_id = conversation_id
        self.user_token = user_token
        self.user_info = user_info or {}
        self.messages: list = []
        self.last_active = time.time()
        self.lock = asyncio.Lock()  # 并发控制锁
        self.pending_tool_call: Optional[dict] = None  # 待确认写操作的暂存区

    def touch(self):
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return time.time() - self.last_active > SESSION_TTL


sessions: dict = {}


def get_session_path(conversation_id: str) -> str:
    # 只保留字母数字和横线/下划线作为安全文件名
    safe_id = "".join(c for c in conversation_id if c.isalnum() or c in "-_")
    return os.path.join(SESSION_DIR, f"{safe_id}.json")


def _save_session_to_disk_sync(session: Session):
    try:
        path = get_session_path(session.conversation_id)
        data = {
            "conversation_id": session.conversation_id,
            "user_token": session.user_token,
            "user_info": session.user_info,
            "messages": session.messages,
            "last_active": session.last_active,
            "pending_tool_call": session.pending_tool_call,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存会话到磁盘失败 {session.conversation_id}: {e}")


async def save_session_to_disk(session: Session):
    await asyncio.to_thread(_save_session_to_disk_sync, session)


def load_session_from_disk(conversation_id: str) -> Optional[Session]:
    try:
        path = get_session_path(conversation_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        session = Session(
            conversation_id=data["conversation_id"],
            user_token=data.get("user_token", ""),
            user_info=data.get("user_info"),
        )
        session.messages = data.get("messages", [])
        session.last_active = data.get("last_active", time.time())
        session.pending_tool_call = data.get("pending_tool_call")
        return session
    except Exception as e:
        logger.error(f"从磁盘加载会话失败 {conversation_id}: {e}")
        return None


async def get_or_create_session(conversation_id: str, user_token: str, user_info: dict = None) -> Session:
    session = None
    if conversation_id in sessions:
        session = sessions[conversation_id]
    else:
        # 尝试从磁盘恢复
        session = load_session_from_disk(conversation_id)
        if session:
            sessions[conversation_id] = session
            logger.info(f"从磁盘恢复了会话: {conversation_id}")
            
    if session:
        if session.is_expired():
            session.messages = []
            session.pending_tool_call = None
            logger.info(f"会话过期已重置: {conversation_id}")
            await save_session_to_disk(session)
        session.user_token = user_token
        if user_info:
            session.user_info = user_info
        session.touch()
        await save_session_to_disk(session)
        return session

    # 新建会话
    session = Session(conversation_id, user_token, user_info)
    sessions[conversation_id] = session
    await save_session_to_disk(session)
    return session


def cleanup_expired_sessions():
    expired = [sid for sid, s in sessions.items() if s.is_expired()]
    for sid in expired:
        del sessions[sid]
        try:
            path = get_session_path(sid)
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"物理删除过期会话文件: {sid}")
        except Exception as e:
            logger.error(f"删除过期会话文件失败 {sid}: {e}")
    if expired:
        logger.info(f"清理内存过期会话: {len(expired)} 个")
