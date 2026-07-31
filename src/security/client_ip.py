"""
客户端 IP 获取工具
"""
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实IP"""
    # 尝试从反向代理头获取
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 直接连接
    if request.client:
        return request.client.host

    return "unknown"
