import uuid
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

from config import MODEL, GO_BACKEND_URL, logger
from utils.http_client import get_http_client
from core.session import (
    sessions, get_or_create_session,
    save_session_to_disk, load_session_from_disk, cleanup_expired_sessions
)
from core.agent import agent_loop

# 导入 tools 包，触发所有业务工具函数的注册器修饰与载入
import tools

# 异步任务状态存储：task_id -> {status, reply, conversation_id, created_at}
# status: 'processing' | 'done' | 'error'
tasks: dict = {}


async def run_agent_task(task_id: str, session, message: str):
    """后台执行 agent_loop，完成后将结果写入 tasks 字典"""
    try:
        reply = await agent_loop(session, message)
        await save_session_to_disk(session)
        tasks[task_id]["status"] = "done"
        tasks[task_id]["reply"] = reply
        logger.info(f"[任务完成] task_id={task_id}")
    except Exception as e:
        logger.error(f"[任务异常] task_id={task_id} | 错误={e}", exc_info=True)
        tasks[task_id]["status"] = "error"
        tasks[task_id]["reply"] = "抱歉，智能助理处理异常，请稍后重试。"


async def expired_sessions_cleaner_loop():
    """后台定时会话清理任务"""
    logger.info("后台会话清理服务启动")
    while True:
        try:
            cleanup_expired_sessions()
            # 清理超过 30 分钟的已完成任务
            now = time.time()
            expired = [tid for tid, t in tasks.items()
                       if t["status"] != "processing" and now - t["created_at"] > 1800]
            for tid in expired:
                del tasks[tid]
            if expired:
                logger.info(f"清理过期任务 {len(expired)} 个")
        except Exception as e:
            logger.error(f"定时清理后台任务异常: {e}")
        await asyncio.sleep(600)  # 每10分钟清理一次


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动后台会话清理任务
    cleaner_task = asyncio.create_task(expired_sessions_cleaner_loop())
    logger.info(f"智能体服务启动 | 模型: {MODEL} | 后端: {GO_BACKEND_URL}")
    await get_http_client()
    yield
    # 关闭
    cleaner_task.cancel()
    try:
        await cleaner_task
    except asyncio.CancelledError:
        pass
    
    from utils.http_client import http_client
    if http_client:
        await http_client.aclose()
    logger.info("智能体服务关闭")


app = FastAPI(title="管理员智能体服务", lifespan=lifespan)


class ChatRequest(BaseModel):
    """小程序发送的聊天请求"""
    message: str                          # 用户消息
    conversation_id: str = None           # 会话ID，为空则自动创建


class ChatResponse(BaseModel):
    """异步任务响应：立即返回 task_id，小程序用它来轮询结果"""
    task_id: str                          # 任务ID，用于轮询
    conversation_id: str                  # 会话ID，小程序需要保存用于续聊


class ClearRequest(BaseModel):
    """清除会话历史"""
    conversation_id: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, x_header_token: str = Header(...)):
    """
    管理员智能体聊天接口（异步模式）

    Header: X-Header-Token: <管理员JWT>
    Body: { "message": "帮我查一下余额", "conversation_id": "xxx" }
    立即返回 task_id，通过 GET /task/{task_id} 轮询结果
    """
    user_token = x_header_token.strip()

    # 生成或使用已有会话ID
    conversation_id = req.conversation_id or str(uuid.uuid4())

    # 获取会话
    session = await get_or_create_session(conversation_id, user_token)

    # 生成任务ID，立即写入任务状态
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "processing",
        "reply": None,
        "conversation_id": conversation_id,
        "created_at": time.time(),
    }
    logger.info(f"[任务创建] task_id={task_id} | conversation_id={conversation_id} | message={req.message[:50]}")

    # 后台异步执行，不阻塞当前请求
    async def _run():
        async with session.lock:
            await run_agent_task(task_id, session, req.message)

    asyncio.create_task(_run())

    # 立即返回，< 1秒，不超时
    return ChatResponse(task_id=task_id, conversation_id=conversation_id)


@app.get("/task/{task_id}")
async def get_task(task_id: str):
    """轮询任务结果"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {
        "task_id": task_id,
        "status": task["status"],          # processing / done / error
        "reply": task["reply"],            # 完成后才有值
        "conversation_id": task["conversation_id"],
    }


@app.post("/clear")
async def clear_session(req: ClearRequest):
    """清除会话历史，开始新对话"""
    session = None
    if req.conversation_id in sessions:
        session = sessions[req.conversation_id]
    else:
        session = load_session_from_disk(req.conversation_id)
        if session:
            sessions[req.conversation_id] = session

    if session:
        async with session.lock:
            session.messages = []
            session.pending_tool_call = None
            try:
                from core.session import get_session_path
                import os
                path = get_session_path(session.conversation_id)
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"物理删除清除的会话文件: {session.conversation_id}")
            except Exception as e:
                logger.error(f"删除会话文件失败 {session.conversation_id}: {e}")
            
            if session.conversation_id in sessions:
                del sessions[session.conversation_id]
        return {"message": "会话已清除"}
    return {"message": "会话不存在"}


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "model": MODEL,
        "active_sessions": len(sessions),
        "backend_url": GO_BACKEND_URL,
    }
