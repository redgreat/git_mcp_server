"""
测试脚本 - 认证服务
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import create_engine


def test_auth():
    from config import Config
    from admin.auth import AuthService
    from admin.models import ensure_schema, create_default_admin

    cfg = Config.load()
    engine = create_engine(cfg.get_admin_db_url(), pool_pre_ping=True)
    ensure_schema(engine)

    auth = AuthService(
        master_key=cfg.security.master_key,
        jwt_secret=cfg.security.jwt_secret,
        session_timeout=3600
    )

    # 1. 密码哈希
    h = auth.hash_password("test123")
    assert isinstance(h, str) and len(h) > 30
    print("✅ 密码哈希正常")

    # 2. 密码验证
    assert auth.verify_password("test123", h)
    assert not auth.verify_password("wrong", h)
    print("✅ 密码验证正常")

    # 3. 登录
    token_data = auth.login(engine, "admin", "admin123")
    assert "token" in token_data
    assert token_data["username"] == "admin"
    print(f"✅ 登录成功: username={token_data['username']}, role={token_data['role']}")

    # 4. Token 验证
    payload = auth.verify_token(token_data["token"])
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"
    print(f"✅ Token 验证成功: sub={payload['sub']}")

    # 5. Admin 权限检查
    auth.require_admin(payload)
    print("✅ Admin 权限检查通过")

    # 6. 无效 Token
    try:
        auth.verify_token("invalid.token.here")
        print("❌ 应抛出异常")
        return False
    except Exception:
        print("✅ 无效 Token 正确拒绝")

    engine.dispose()
    print("\n🎉 认证测试全部通过！")
    return True


if __name__ == "__main__":
    try:
        test_auth()
    except Exception as e:
        print(f"❌ 认证测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
