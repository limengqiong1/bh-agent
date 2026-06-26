import json
import time
from typing import Optional
from config import logger, CACHE_TTL

read_cache: dict = {}


def get_cached_result(tool_name: str, token: str) -> Optional[str]:
    key = (tool_name, token)
    if key in read_cache:
        result_str, timestamp = read_cache[key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"缓存命中: {tool_name} (token: {token[:10]}...)")
            return result_str
        else:
            del read_cache[key]
    return None


def set_cached_result(tool_name: str, token: str, result_str: str):
    key = (tool_name, token)
    read_cache[key] = (result_str, time.time())


class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.core_names = set()
        self.uncommon_names = set()
        self.write_names = set()

    def register(self, name: str, description: str, input_schema: dict, is_core: bool = True, is_write: bool = False):
        def decorator(func):
            self.tools[name] = {
                "name": name,
                "description": description,
                "input_schema": input_schema,
                "is_core": is_core,
                "is_write": is_write,
                "func": func
            }
            if is_core:
                self.core_names.add(name)
            else:
                self.uncommon_names.add(name)
            if is_write:
                self.write_names.add(name)
            return func
        return decorator

    def to_openai_tools(self, active_tools: list) -> list:
        normalized = []
        for tool in active_tools:
            parameters = tool.get("input_schema") or {
                "type": "object", "properties": {},
            }
            parameters = json.loads(json.dumps(parameters))
            if isinstance(parameters, dict) and parameters.get("type") == "object":
                parameters.setdefault("additionalProperties", False)
            normalized.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": parameters,
                },
            })
        return normalized

    async def execute(self, tool_name: str, args: dict, token: str) -> str:
        if tool_name not in self.tools:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
            
        # 缓存处理：仅对 get_dashboard 进行缓存
        if tool_name == "get_dashboard":
            cached = get_cached_result(tool_name, token)
            if cached is not None:
                return cached

        tool_info = self.tools[tool_name]
        func = tool_info["func"]
        try:
            result = await func(args, token)
            if not isinstance(result, str):
                result_str = json.dumps(result, ensure_ascii=False, default=str)
            else:
                result_str = result
                
            if tool_name == "get_dashboard":
                set_cached_result(tool_name, token, result_str)
                
            return result_str
        except Exception as e:
            logger.error(f"工具执行异常 {tool_name}: {e}", exc_info=True)
            return json.dumps({"error": str(e)}, ensure_ascii=False)


registry = ToolRegistry()
