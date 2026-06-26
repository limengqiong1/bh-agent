import httpx
from typing import Optional
from config import GO_BACKEND_URL, logger

http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(
            base_url=GO_BACKEND_URL,
            timeout=30.0,
        )
    return http_client


async def call_go_api(method: str, path: str, token: str,
                      json_body: dict = None, params: dict = None) -> dict:
    """统一调用 Go 后端接口"""
    client = await get_http_client()
    headers = {"X-Header-Token": token}
    try:
        resp = await client.request(
            method=method, url=path, headers=headers,
            json=json_body, params=params,
        )
        if resp.status_code >= 400:
            return {"error": True, "status": resp.status_code, "message": resp.text}
        if resp.status_code == 204 or not resp.text:
            return {"success": True}
        return resp.json()
    except httpx.RequestError as e:
        return {"error": True, "message": f"请求后端失败: {str(e)}"}
