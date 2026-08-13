from core.registry import registry
from utils.http_client import call_go_api


@registry.register(
    name="get_dashboard",
    description="获取仪表盘概览数据：总充值、总消费、总余额、商户数量。",
    input_schema={"type": "object", "properties": {}},
    is_core=True, is_write=False
)
async def tool_get_dashboard(args: dict, token: str):
    return await call_go_api("GET", "/api/dashboard", token)


@registry.register(
    name="search_merchants",
    description="管理员搜索商户列表。可按商户名、联系人、电话模糊查询，可按区域和状态过滤。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_name": {"type": "string", "description": "商户名称（模糊匹配）"},
            "contact_name": {"type": "string", "description": "联系人姓名（模糊匹配）"},
            "contact_phone": {"type": "string", "description": "联系电话（模糊匹配）"},
            "area_id": {"type": "integer", "description": "区域ID"},
            "status": {"type": "integer", "description": "商户状态：1启用，0禁用。若不限制状态（查询所有商户），请务必传 -1。"},
            "offset": {"type": "integer", "description": "分页偏移，默认0"},
            "limit": {"type": "integer", "description": "每页条数，默认20"},
        },
    },
    is_core=True, is_write=False
)
async def tool_search_merchants(args: dict, token: str):
    body = {k: v for k, v in args.items() if v is not None}
    body.setdefault("status", -1)
    body.setdefault("offset", 0)
    body.setdefault("limit", 20)
    return await call_go_api("POST", "/api/admin/merchants/list", token, json_body=body)


@registry.register(
    name="get_merchant_detail",
    description="获取某个商户的详细信息。需要商户ID。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID"},
        },
        "required": ["merchant_id"],
    },
    is_core=True, is_write=False
)
async def tool_get_merchant_detail(args: dict, token: str):
    return await call_go_api("GET", f"/api/merchants/{args['merchant_id']}", token)


@registry.register(
    name="get_merchant_balance",
    description="查询某个商户的余额信息。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID"},
        },
        "required": ["merchant_id"],
    },
    is_core=True, is_write=False
)
async def tool_get_merchant_balance(args: dict, token: str):
    return await call_go_api("GET", f"/api/merchants/{args['merchant_id']}/balance", token)


@registry.register(
    name="get_merchant_recharges",
    description="查询某个商户的充值记录。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["merchant_id"],
    },
    is_core=True, is_write=False
)
async def tool_get_merchant_recharges(args: dict, token: str):
    body = {"offset": args.get("offset", 0), "limit": args.get("limit", 20)}
    return await call_go_api("POST", f"/api/merchants/{args['merchant_id']}/recharges", token, json_body=body)


@registry.register(
    name="get_merchant_orders",
    description="查询某个商户的订单记录。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["merchant_id"],
    },
    is_core=True, is_write=False
)
async def tool_get_merchant_orders(args: dict, token: str):
    body = {"offset": args.get("offset", 0), "limit": args.get("limit", 20)}
    return await call_go_api("POST", f"/api/merchants/{args['merchant_id']}/orders", token, json_body=body)


@registry.register(
    name="get_merchant_ledgers",
    description="查询某个商户的钱包流水（含充值、消费、调整的每笔变动）。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["merchant_id"],
    },
    is_core=True, is_write=False
)
async def tool_get_merchant_ledgers(args: dict, token: str):
    body = {"offset": args.get("offset", 0), "limit": args.get("limit", 20)}
    return await call_go_api("POST", f"/api/merchants/{args['merchant_id']}/ledgers", token, json_body=body)


@registry.register(
    name="get_all_recharges",
    description=(
        "管理员查看全平台所有充值记录，支持按商户、业务员、状态过滤，支持分页。"
        "【重要】当需要跨商户统计或排行（例如：充值金额最高的商户、各商户充值汇总、全平台充值总额）时，"
        "必须优先使用此工具一次性获取全量数据，严禁对每个商户单独调用 get_merchant_recharges。"
        "如需全量数据用于统计，请设置 limit=1000。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "可选，按商户过滤"},
            "salesman_user_id": {"type": "integer", "description": "可选，按业务员过滤"},
            "status": {"type": "string", "description": "可选，按状态过滤：pending/approved/rejected"},
            "offset": {"type": "integer", "description": "偏移量，默认0"},
            "limit": {"type": "integer", "description": "每页限制数，默认20。需要全量统计时请设置为1000"},
        },
    },
    is_core=True, is_write=False
)
async def tool_get_all_recharges(args: dict, token: str):
    body = {k: v for k, v in args.items() if v is not None}
    body.setdefault("offset", 0)
    body.setdefault("limit", 20)
    return await call_go_api("POST", "/api/admin/recharges", token, json_body=body)


@registry.register(
    name="get_all_orders",
    description=(
        "管理员查看全平台所有订单，支持按商户、业务员、状态过滤，支持分页。"
        "【重要】当需要跨商户统计或排行（例如：销售额最高的商户、各商户订单汇总、全平台销售总额）时，"
        "必须优先使用此工具一次性获取全量数据，严禁对每个商户单独调用 get_merchant_orders。"
        "如需全量数据用于统计，请设置 limit=1000。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "可选，按商户过滤"},
            "salesman_user_id": {"type": "integer", "description": "可选，按业务员过滤"},
            "status": {"type": "string", "description": "可选，按状态过滤：pending/completed/cancelled"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
    },
    is_core=True, is_write=False
)
async def tool_get_all_orders(args: dict, token: str):
    body = {k: v for k, v in args.items() if v is not None}
    body.setdefault("offset", 0)
    body.setdefault("limit", 20)
    return await call_go_api("POST", "/api/admin/orders", token, json_body=body)


@registry.register(
    name="search_users",
    description="管理员查询后台用户列表，支持角色、商户ID、手机号前缀过滤，支持分页。",
    input_schema={
        "type": "object",
        "properties": {
            "role": {"type": "string", "description": "角色过滤：admin/sales/merchant"},
            "merchant_id": {"type": "integer", "description": "按关联商户ID过滤"},
            "phone_prefix": {"type": "string", "description": "手机号前缀模糊查询"},
            "offset": {"type": "integer", "description": "偏移量，默认0"},
            "limit": {"type": "integer", "description": "每页限制数，默认10"},
        },
    },
    is_core=True, is_write=False
)
async def tool_search_users(args: dict, token: str):
    body = {k: v for k, v in args.items() if v is not None}
    body.setdefault("offset", 0)
    body.setdefault("limit", 10)
    return await call_go_api("POST", "/api/users/list", token, json_body=body)


@registry.register(
    name="reflush_admin_cache",
    description="管理员手动刷新后台系统缓存。",
    input_schema={"type": "object", "properties": {}},
    is_core=False, is_write=False
)
async def tool_reflush_admin_cache(args: dict, token: str):
    return await call_go_api("GET", "/api/admin/reflush/admin_cache", token)


@registry.register(
    name="get_low_balance_merchants",
    description="查询余额即将不足（低于100元）的商户钱包列表（业务员查关联 of，管理员查所有）。",
    input_schema={"type": "object", "properties": {}},
    is_core=False, is_write=False
)
async def tool_get_low_balance_merchants(args: dict, token: str):
    return await call_go_api("GET", "/api/merchants/low-balance", token)
