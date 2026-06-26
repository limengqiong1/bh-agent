from core.registry import registry
from utils.http_client import call_go_api


@registry.register(
    name="approve_recharge",
    description="审批通过一笔充值申请。需要充值记录ID。",
    input_schema={
        "type": "object",
        "properties": {
            "recharge_id": {"type": "integer", "description": "充值记录ID"},
        },
        "required": ["recharge_id"],
    },
    is_core=True, is_write=True
)
async def tool_approve_recharge(args: dict, token: str):
    return await call_go_api("POST", "/api/recharges/approve", token, json_body={"recharge_id": args["recharge_id"]})


@registry.register(
    name="reject_recharge",
    description="拒绝一笔充值申请。需要充值记录ID和拒绝原因。",
    input_schema={
        "type": "object",
        "properties": {
            "recharge_id": {"type": "integer", "description": "充值记录ID"},
            "reject_reason": {"type": "string", "description": "拒绝原因"},
        },
        "required": ["recharge_id"],
    },
    is_core=True, is_write=True
)
async def tool_reject_recharge(args: dict, token: str):
    return await call_go_api("POST", "/api/recharges/reject", token,
                             json_body={"recharge_id": args["recharge_id"],
                                         "reject_reason": args.get("reject_reason", "")})


@registry.register(
    name="complete_order",
    description="标记一个订单为已完成。需要订单ID。",
    input_schema={
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "订单ID"},
        },
        "required": ["order_id"],
    },
    is_core=True, is_write=True
)
async def tool_complete_order(args: dict, token: str):
    return await call_go_api("POST", "/api/orders/complete", token, json_body={"order_id": args["order_id"]})


@registry.register(
    name="create_admin_user",
    description="管理员预录入后台管理人员/业务员账号（手机号用于微信登录时自动匹配角色）。",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "人员姓名，必填"},
            "phone": {"type": "string", "description": "手机号，必填"},
            "role": {"type": "string", "description": "角色编码：admin(管理员) 或 sales(业务员)，必填"},
        },
        "required": ["name", "phone", "role"],
    },
    is_core=True, is_write=True
)
async def tool_create_admin_user(args: dict, token: str):
    body = {
        "name": args["name"],
        "phone": args["phone"],
        "role": args["role"],
    }
    return await call_go_api("POST", "/api/admin/users/add", token, json_body=body)


@registry.register(
    name="update_user_merchant",
    description="管理员更新用户的关联商户（仅允许操作为merchant角色的用户）。",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "人员用户ID，必填"},
            "merchant_id": {"type": "integer", "description": "要绑定的商户ID，必填"},
        },
        "required": ["user_id", "merchant_id"],
    },
    is_core=True, is_write=True
)
async def tool_update_user_merchant(args: dict, token: str):
    body = {
        "user_id": args["user_id"],
        "merchant_id": args["merchant_id"],
    }
    return await call_go_api("POST", "/api/admin/users/merchant", token, json_body=body)


@registry.register(
    name="create_recharge",
    description="管理员或业务员为商户录入/创建一笔充值订单。需要商户ID、资金类型ID、申请金额。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID，必填"},
            "amount_type_id": {"type": "integer", "description": "资金类型ID，例如：1(预存款) 2(授信额度)，必填"},
            "apply_amount": {"type": "number", "description": "申请充值的金额，必填"},
            "remark": {"type": "string", "description": "备注说明"},
        },
        "required": ["merchant_id", "amount_type_id", "apply_amount"],
    },
    is_core=True, is_write=True
)
async def tool_create_recharge(args: dict, token: str):
    body = {
        "merchant_id": args["merchant_id"],
        "amount_type_id": args["amount_type_id"],
        "apply_amount": args["apply_amount"],
        "remark": args.get("remark", ""),
    }
    return await call_go_api("POST", "/api/recharges", token, json_body=body)


@registry.register(
    name="create_merchant",
    description="管理员创建新商户。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_name": {"type": "string", "description": "商户名称，必填"},
            "contact_name": {"type": "string", "description": "联系人姓名"},
            "contact_phone": {"type": "string", "description": "联系人电话"},
            "area_id": {"type": "integer", "description": "区域ID"},
            "address": {"type": "string", "description": "商户地址"},
        },
        "required": ["merchant_name"],
    },
    is_core=False, is_write=True
)
async def tool_create_merchant(args: dict, token: str):
    body = {
        "merchant_name": args["merchant_name"],
        "contact_name": args.get("contact_name", ""),
        "contact_phone": args.get("contact_phone", ""),
        "area_id": args.get("area_id", 0),
        "address": args.get("address", ""),
    }
    return await call_go_api("POST", "/api/admin/merchants", token, json_body=body)


@registry.register(
    name="update_merchant",
    description="管理员编辑商户信息。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID，必填"},
            "merchant_name": {"type": "string", "description": "商户名称，必填"},
            "contact_name": {"type": "string", "description": "联系人姓名"},
            "contact_phone": {"type": "string", "description": "联系人电话"},
            "area_id": {"type": "integer", "description": "区域ID"},
            "address": {"type": "string", "description": "商户地址"},
        },
        "required": ["merchant_id", "merchant_name"],
    },
    is_core=False, is_write=True
)
async def tool_update_merchant(args: dict, token: str):
    body = {
        "merchant_name": args["merchant_name"],
        "contact_name": args.get("contact_name", ""),
        "contact_phone": args.get("contact_phone", ""),
        "area_id": args.get("area_id", 0),
        "address": args.get("address", ""),
    }
    return await call_go_api("PUT", f"/api/admin/merchants/{args['merchant_id']}", token, json_body=body)


@registry.register(
    name="delete_merchant",
    description="管理员删除指定的商户（软删除）。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "需要删除的商户ID"},
        },
        "required": ["merchant_id"],
    },
    is_core=False, is_write=True
)
async def tool_delete_merchant(args: dict, token: str):
    return await call_go_api("DELETE", f"/api/admin/merchants/{args['merchant_id']}", token)


@registry.register(
    name="toggle_merchant_status",
    description="启用或禁用一个商户。需要商户ID和目标状态。",
    input_schema={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "integer", "description": "商户ID"},
            "status": {"type": "integer", "description": "目标状态：1启用 0禁用"},
        },
        "required": ["merchant_id", "status"],
    },
    is_core=False, is_write=True
)
async def tool_toggle_merchant_status(args: dict, token: str):
    return await call_go_api("POST", f"/api/admin/merchants/{args['merchant_id']}/status",
                             token, json_body={"status": args["status"]})


@registry.register(
    name="unbind_user_merchant",
    description="管理员解绑用户的商户关联，将商户ID置为空（仅针对merchant角色）。",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "人员用户ID，必填"},
            "merchant_id": {"type": "integer", "description": "当前关联的商户ID，必填"},
        },
        "required": ["user_id", "merchant_id"],
    },
    is_core=False, is_write=True
)
async def tool_unbind_user_merchant(args: dict, token: str):
    body = {
        "user_id": args["user_id"],
        "merchant_id": args["merchant_id"],
    }
    return await call_go_api("POST", "/api/admin/users/unbind-merchant", token, json_body=body)
