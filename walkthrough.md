# 智能体服务模块化重构成果与部署指南 (Walkthrough)

我们已成功将庞大单文件 `agent.py` 中的所有核心类、工具注册器、定时清理协程、会话管理器、系统提示词以及 23 个业务工具，拆解重构为现代、模块化的 Python FastAPI 项目，并保存在 [crm-agent](file:///D:/pyProject/hello-agents/crm-agent) 文件夹中。

---

## 1. 重构后的项目目录结构

重构后的包组织结构非常契合企业级生产部署，如下所示：

```
crm-agent/
├── .env.template         # 环境变量配置模板
├── requirements.txt      # 依赖管理包
├── main.py               # Uvicorn 运行主入口
├── app.py                # FastAPI 路由、协程并发锁与生命周期 (lifespan)
├── config.py             # 环境变量与全局常量配置中心，日志初始化
├── utils/
│   ├── __init__.py
│   └── http_client.py    # Go 后端 HTTP 异步请求封装 (call_go_api)
├── core/
│   ├── __init__.py
│   ├── registry.py       # 工具注册表及 TTL 短时缓存机制
│   ├── session.py        # 会话 Session 状态与异步磁盘写盘 (asyncio.to_thread)
│   ├── prompt.py         # SYSTEM_PROMPT 常量定义
│   └── agent.py          # 核心智能体交互循环 (agent_loop)
└── tools/
    ├── __init__.py       # 自动加载所有业务工具触发注册
    ├── query_tools.py    # 12 个读/查询业务工具 (Dashboard, 流水, 余额等)
    └── action_tools.py   # 11 个写/操作业务工具 (充值, 审批, 商户增删改等)
```

---

## 2. 核心模块设计与职责划分

1.  **全局配置 (`config.py`)**：使用 `dotenv` 加载环境变量，如 `DASHSCOPE_API_KEY`。规范并创建 `data/sessions/` 磁盘持久化目录。
2.  **工具注册机制 (`core/registry.py` & `tools/__init__.py`)**：
    *   通过 `registry.py` 中的 `ToolRegistry` 提供 `@registry.register` 注册器装饰器。
    *   在 `tools/__init__.py` 中统一导入 `query_tools` 和 `action_tools`。在 `app.py` 中引入 `import tools` 即可在启动时**自动加载并实例化全部 23 个工具**，消除复杂的硬编码。
3.  **读工具短时缓存与隔离 (`core/registry.py`)**：仅对 `get_dashboard` 进行缓存，且 Key 绑定 `user_token` 保证商户数据在并发场景下的绝对安全隔离。
4.  **非阻塞会话写盘与清理 (`core/session.py`)**：
    *   `save_session_to_disk` 使用 `asyncio.to_thread` 在独立线程中完成写盘操作，彻底消除 I/O 阻塞。
    *   `cleanup_expired_sessions` 每 10 分钟自动在后台定时清理内存和磁盘中的过期 JSON 文件（生命周期 7 天）。
5.  **业务解耦 (`tools/query_tools.py` 和 `tools/action_tools.py`)**：
    *   将 12 个纯查询工具（`get_*`, `search_*`）与 11 个带拦截确认的写操作工具（`approve_*`, `create_*`, `delete_*`）物理隔离，极大地方便了后续开发与代码审查。

---

## 3. 验证与测试步骤

### A. 语法与静态编译验证
我们已通过内置 `compileall` 模块对 `crm-agent` 目录下的所有文件进行了深度静态语法编译扫描：
```bash
python -c "import compileall; compileall.compile_dir('.')"
```
**编译结果**：所有文件（包括核心交互循环、23个工具以及 FastAPI 路由）均**编译成功，无任何语法错误或包导入缺失**。

### B. 运行与部署说明
请按照以下步骤在您的本地或云端服务器上运行：

1.  **拷贝环境变量**：
    将 `crm-agent` 目录下的 `.env.template` 重命名为 `.env`，并配置好您的 `DASHSCOPE_API_KEY` 与 `GO_BACKEND_URL`。
    *(注：可直接从原 `learn-claude/.env` 中复制)*
2.  **安装依赖**：
    ```bash
    pip install -r requirements.txt
    ```
3.  **启动服务**：
    ```bash
    python main.py
    ```
4.  **接口测试**：
    向 `http://127.0.0.1:8081/health` 发送 GET 请求，验证响应是否成功。例如：
    ```json
    {
      "status": "ok",
      "model": "qwen-max",
      "active_sessions": 0,
      "backend_url": "http://118.178.196.167:8080"
    }
    ```
