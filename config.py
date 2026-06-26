import os
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not API_KEY:
    raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")

GO_BACKEND_URL = os.getenv("GO_BACKEND_URL", "http://localhost:8080")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "qwen-max")
MODEL = os.getenv("QWEN_MODEL", LLM_MODEL_ID)

TOKEN_THRESHOLD = 100000
MAX_ROUNDS = 15  # 单次对话最大工具调用轮次，防止无限循环
SESSION_TTL = 7 * 24 * 3600  # 会话过期时间：7天

# 会话存储目录设置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "data", "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

CACHE_TTL = 30.0  # 缓存有效期为 30 秒

# 配置全局日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent")
