import json
import re
import asyncio
from openai import AsyncOpenAI
from config import API_KEY, MODEL, TOKEN_THRESHOLD, MAX_ROUNDS, logger
from .registry import registry
from .session import Session
from .prompt import SYSTEM_PROMPT

llm_client = AsyncOpenAI(
    api_key=API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


def get_active_tools(user_message: str, messages: list) -> list:
    """结合当前输入和上下文历史，动态加载需要的不常用工具，裁剪冗余工具以省Token"""
    # 核心工具定义
    active = [t for t in registry.tools.values() if t["is_core"]]
    
    # 构造待检测的检索文本
    recent_text = user_message
    if messages:
        # 将最近3条对话历史序列化，以捕捉对话的连贯意图和已挂起的 Tool Call
        recent_text += " " + json.dumps(messages[-3:], ensure_ascii=False)
        
    recent_text = recent_text.lower()
    
    # 1. create_merchant
    if ("create_merchant" in recent_text) or (
        any(x in recent_text for x in ["商户", "店铺", "商家"]) and
        any(y in recent_text for y in ["创建", "新建", "添加", "录入", "新增", "建一个", "建个", "建新", "注册", "开户"])
    ):
        if "create_merchant" in registry.tools:
            active.append(registry.tools["create_merchant"])

    # 2. update_merchant
    if ("update_merchant" in recent_text) or (
        any(x in recent_text for x in ["商户", "店铺", "商家"]) and
        any(y in recent_text for y in ["修改", "编辑", "更新", "更正", "改"])
    ):
        if "update_merchant" in registry.tools:
            active.append(registry.tools["update_merchant"])

    # 3. delete_merchant
    if ("delete_merchant" in recent_text) or (
        any(x in recent_text for x in ["商户", "店铺", "商家"]) and
        any(y in recent_text for y in ["删除", "注销", "移除", "删"])
    ):
        if "delete_merchant" in registry.tools:
            active.append(registry.tools["delete_merchant"])

    # 4. toggle_merchant_status
    if any(x in recent_text for x in ["禁用", "启用", "封禁", "解封", "上线", "下线", "冻结", "激活", "toggle_merchant_status"]):
        if "toggle_merchant_status" in registry.tools:
            active.append(registry.tools["toggle_merchant_status"])

    # 5. reflush_admin_cache
    if any(x in recent_text for x in ["缓存", "reflush_admin_cache"]):
        if "reflush_admin_cache" in registry.tools:
            active.append(registry.tools["reflush_admin_cache"])

    # 6. unbind_user_merchant
    if any(x in recent_text for x in ["解绑", "unbind_user_merchant"]):
        if "unbind_user_merchant" in registry.tools:
            active.append(registry.tools["unbind_user_merchant"])

    # 7. get_low_balance_merchants
    if any(x in recent_text for x in ["余额不足", "低余额", "预警", "警报", "低额", "低于", "get_low_balance_merchants"]):
        if "get_low_balance_merchants" in registry.tools:
            active.append(registry.tools["get_low_balance_merchants"])
            
    return active


def extract_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") in ("text", "output_text") and part.get("text"):
                    parts.append(part["text"])
                elif isinstance(part.get("text"), str):
                    parts.append(part["text"])
            elif hasattr(part, "text"):
                text = getattr(part, "text", "")
                if text:
                    parts.append(text)
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


def estimate_tokens(messages: list) -> int:
    return len(json.dumps(messages, default=str)) // 4


def microcompact(messages: list):
    """清理旧的 tool 结果，只保留最近几条"""
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    if len(tool_msgs) <= 3:
        return
    for msg in tool_msgs[:-3]:
        if isinstance(msg.get("content"), str) and len(msg["content"]) > 100:
            msg["content"] = "[已压缩]"


async def auto_compact(messages: list, system: str, token: str) -> list:
    """用 LLM 压缩对话历史"""
    conv_text = json.dumps(messages, default=str)[-40000:]
    resp = await llm_client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是对话压缩助手。请将以下对话压缩为简洁的上下文摘要，保留关键信息（商户名称、金额、查询结果等）。"},
            {"role": "user", "content": f"压缩以下对话：\n{conv_text}"},
        ],
        max_tokens=1500,
    )
    summary = extract_text(resp.choices[0].message.content)
    logger.info(f"对话已压缩，原始 {len(messages)} 条 -> 摘要")
    return [
        {"role": "user", "content": f"[对话已压缩，以下是历史摘要]\n{summary}"},
        {"role": "assistant", "content": "好的，我已了解之前的对话内容。请继续。"},
    ]


async def agent_loop(session: Session, user_message: str) -> str:
    """
    核心 agent 循环：
    1. 用户消息加入历史
    2. 调用 LLM，如果返回 tool_calls 则执行工具
    3. 循环直到 LLM 返回纯文本（最终回复）
    """
    messages = session.messages
    token = session.user_token

    # 检查上一轮是否有挂起的待确认写操作
    if session.pending_tool_call:
        pending = session.pending_tool_call
        user_choice = user_message.strip()
        
        # 用户确认执行
        if user_choice in ("确认", "确定", "yes", "confirm", "ok", "是的", "对"):
            logger.info(f"用户确认了挂起的写操作工具执行: {pending['name']}")
            # 实际执行工具
            output = await registry.execute(pending["name"], pending["args"], token)
            
            # 将历史记录中挂起状态的 Tool 消息替换为真实执行结果
            found = False
            for msg in reversed(messages):
                if msg.get("role") == "tool" and msg.get("tool_call_id") == pending["id"]:
                    msg["content"] = output
                    found = True
                    break
            if not found:
                messages.append({
                    "role": "tool",
                    "tool_call_id": pending["id"],
                    "name": pending["name"],
                    "content": output,
                })
            
            # 清除挂起状态
            session.pending_tool_call = None
            
            # 将用户确认输入追加到消息历史
            user_context = ""
            if session.user_info:
                user_context = f"\n<用户信息>{json.dumps(session.user_info, ensure_ascii=False)}</用户信息>"
            messages.append({"role": "user", "content": user_message + user_context})

        # 用户取消执行
        elif user_choice in ("取消", "不", "no", "cancel", "算了", "不对", "否"):
            logger.info(f"用户取消了挂起的写操作工具执行: {pending['name']}")
            # 将历史记录中的挂起 tool 消息置为已取消状态
            for msg in reversed(messages):
                if msg.get("role") == "tool" and msg.get("tool_call_id") == pending["id"]:
                    msg["content"] = json.dumps({"error": "user_cancelled", "message": "该操作已被管理员用户取消执行。"}, ensure_ascii=False)
                    break
            
            # 清除挂起状态
            session.pending_tool_call = None
            
            # 将用户取消输入追加到消息历史
            user_context = ""
            if session.user_info:
                user_context = f"\n<用户信息>{json.dumps(session.user_info, ensure_ascii=False)}</用户信息>"
            messages.append({"role": "user", "content": user_message + user_context})
        
        # 用户输入了其他无关的话，需要先强行确认或取消
        else:
            return f"您当前有一个待确认的后台管理操作：【{pending['name']}】，参数为：{json.dumps(pending['args'], ensure_ascii=False)}。\n请先回复“确认”执行该操作，或者回复“取消”以中止。"
    else:
        # 正常流程，将新消息加入历史
        user_context = ""
        if session.user_info:
            user_context = f"\n<用户信息>{json.dumps(session.user_info, ensure_ascii=False)}</用户信息>"
        messages.append({"role": "user", "content": user_message + user_context})

    active_tools = get_active_tools(user_message, messages)
    openai_tools = registry.to_openai_tools(active_tools)
    rounds = 0
    total_tokens_used = 0

    while rounds < MAX_ROUNDS:
        # 压缩检查
        microcompact(messages)
        if estimate_tokens(messages) > TOKEN_THRESHOLD:
            logger.info(f"会话 {session.conversation_id} 触发自动压缩")
            messages[:] = await auto_compact(messages, SYSTEM_PROMPT, token)

        # 异步调用 LLM
        request_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        logger.info(
            f"[LLM请求] 会话={session.conversation_id} | 轮次={rounds+1} | "
            f"模型={MODEL} | 消息数={len(request_messages)} | "
            f"工具数={len(openai_tools)} | "
            f"用户消息={user_message[:100]}"
        )
        import time as _time
        _llm_start = _time.time()
        try:
            resp = await llm_client.chat.completions.create(
                model=MODEL,
                messages=request_messages,
                tools=openai_tools,
                tool_choice="auto",
                max_tokens=4000,
                timeout=120.0,  # 云托管环境需要更长超时（网络延迟 + 模型推理时间）
            )
            _llm_cost = round(_time.time() - _llm_start, 2)
            logger.info(
                f"[LLM响应] 耗时={_llm_cost}s | "
                f"finish_reason={resp.choices[0].finish_reason} | "
                f"tokens={getattr(resp.usage, 'total_tokens', '?') if resp.usage else '?'} | "
                f"prompt_tokens={getattr(resp.usage, 'prompt_tokens', '?') if resp.usage else '?'} | "
                f"completion_tokens={getattr(resp.usage, 'completion_tokens', '?') if resp.usage else '?'}"
            )
        except asyncio.TimeoutError:
            _llm_cost = round(_time.time() - _llm_start, 2)
            logger.error(f"[LLM超时] 耗时={_llm_cost}s | 模型={MODEL}")
            return "抱歉，智能助理服务请求大模型超时，请稍后重试。"
        except Exception as e:
            _llm_cost = round(_time.time() - _llm_start, 2)
            logger.error(f"[LLM异常] 耗时={_llm_cost}s | 模型={MODEL} | 错误={e}")
            return "抱歉，智能助理服务请求大模型异常，请稍后重试。"

        rounds += 1
        if hasattr(resp, "usage") and resp.usage:
            total_tokens_used += resp.usage.total_tokens

        choice = resp.choices[0]
        assistant_msg = choice.message
        
        # 记录 assistant 消息
        entry = {
            "role": "assistant",
            "content": assistant_msg.content or "",
        }
        
        # 统一处理工具调用（原生及文本兜底解析）
        tool_calls = []
        if assistant_msg.tool_calls:
            for tc in assistant_msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })
        else:
            # 兜底解析文本格式的工具调用，例如：:default_api:create_merchant {...}
            content = assistant_msg.content or ""
            if ":default_api:" in content or ":tools:" in content or any(f":{t}" in content for t in registry.tools.keys()):
                pattern = r'(?::[a-zA-Z0-9_-]+)?:([a-zA-Z0-9_-]+)\s*(\{[\s\S]*?\})'
                for match in re.finditer(pattern, content):
                    t_name = match.group(1)
                    t_args_str = match.group(2)
                    if t_name in registry.tools:
                        try:
                            # 清理可能包含的 markdown 代码块包裹
                            clean_args = t_args_str.strip()
                            if clean_args.startswith("```"):
                                lines = clean_args.split("\n")
                                if lines[0].startswith("```"):
                                    lines = lines[1:]
                                if lines[-1].strip() == "```":
                                    lines = lines[:-1]
                                clean_args = "\n".join(lines)
                            clean_args = clean_args.strip()
                            # 验证 JSON
                            t_args = json.loads(clean_args)
                            
                            tool_calls.append({
                                "id": f"text_call_{t_name}_{rounds}",
                                "type": "function",
                                "function": {
                                    "name": t_name,
                                    "arguments": json.dumps(t_args, ensure_ascii=False)
                                }
                            })
                        except Exception as e:
                            logger.error(f"解析文本工具参数失败: {t_args_str}, 错误: {e}")
                            
        if tool_calls:
            entry["tool_calls"] = tool_calls
            tool_names = [tc["function"]["name"] for tc in tool_calls]
            logger.info(f"[LLM工具调用] 调用工具: {tool_names}")
            for tc in tool_calls:
                logger.info(f"  ├─ {tc['function']['name']}({tc['function']['arguments'][:300]})")
        else:
            reply_preview = (assistant_msg.content or '')[:200]
            logger.info(f"[LLM最终回复] 预览: {reply_preview}")
            
        messages.append(entry)

        # 没有工具调用 -> 最终回复
        if not tool_calls:
            final_text = extract_text(assistant_msg.content) or "抱歉，我暂时无法回答这个问题。"
            session.touch()
            logger.info(
                f"会话 {session.conversation_id} | 轮次: {rounds} | "
                f"最终轮 tokens: {getattr(resp.usage, 'total_tokens', '?')} | "
                f"本次交互累计消耗 tokens: {total_tokens_used}"
            )
            return final_text

        # 执行工具调用
        for tool_call in tool_calls:
            tc_func = tool_call["function"]
            tool_name = tc_func["name"]
            try:
                args = json.loads(tc_func["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}

            # 如果检测到是敏感写操作，进行拦截，记录到会话状态中，向大模型填充等待确认并返回
            # 注意：若用户本轮发送的消息就是“确认”等，说明是对此前展示信息的最终确认，此时不再拦截，直接执行
            is_user_confirm = user_message.strip() in ("确认", "确定", "yes", "confirm", "ok", "是的", "对")
            if tool_name in registry.write_names and not is_user_confirm:
                logger.info(f"检测到敏感写操作: {tool_name}，拦截挂起，请求管理员确认。")
                session.pending_tool_call = {
                    "id": tool_call["id"],
                    "name": tool_name,
                    "args": args,
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_name,
                    "content": json.dumps({"status": "awaiting_user_confirmation"}, ensure_ascii=False),
                })
                # 继续大模型调用，让大模型向用户生成人性化的确认话术并结束当前 Agent 轮次
                continue

            # 读操作或已被确认的写操作正常执行
            logger.info(f"[工具执行] {tool_name} | 参数: {json.dumps(args, ensure_ascii=False)[:300]}")
            _tool_start = _time.time()
            output = await registry.execute(tool_name, args, token)
            _tool_cost = round(_time.time() - _tool_start, 2)
            logger.info(f"[工具结果] {tool_name} | 耗时={_tool_cost}s | 结果: {output[:500]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": output,
            })

    # 超过最大轮次
    session.touch()
    return "抱歉，处理过程太复杂了，请简化您的问题再试一次。"
