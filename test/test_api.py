"""
测试脚本 - 后台管理 API 接口
需要先启动服务器: python -m src.server
"""
import sys
import os
import json
import httpx

BASE_URL = "http://localhost:3001"


class APITester:
    def __init__(self, base_url=BASE_URL):
        self.base = base_url
        self.token = None
        self.client = httpx.Client(timeout=30)
        self.passed = 0
        self.failed = 0

    def assert_ok(self, resp, label=""):
        try:
            data = resp.json() if resp.text else {}
            if resp.status_code < 400:
                self.passed += 1
                print(f"  ✅ {label} (status={resp.status_code})")
                return data
            else:
                self.failed += 1
                print(f"  ❌ {label} (status={resp.status_code}): {data.get('detail', resp.text[:100])}")
                return data
        except Exception as e:
            self.failed += 1
            print(f"  ❌ {label}: {e}")
            return None

    def run(self):
        print("=" * 60)
        print("Git MCP Server API 集成测试")
        print("=" * 60)

        # --- 健康检查 ---
        print("\n📌 1. 健康检查")
        self.assert_ok(self.client.get(f"{self.base}/health"), "GET /health")

        # --- 登录 ---
        print("\n📌 2. 管理员登录")
        resp = self.client.post(f"{self.base}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        data = self.assert_ok(resp, "POST /api/auth/login")
        if data and "token" in data:
            self.token = data["token"]
            self.client.headers["Authorization"] = self.token
        else:
            print("❌ 登录失败，停止测试")
            return

        # --- 当前用户 ---
        print("\n📌 3. 获取当前用户")
        self.assert_ok(self.client.get(f"{self.base}/api/auth/me"), "GET /api/auth/me")

        # --- 仪表盘 ---
        print("\n📌 4. 仪表盘")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/dashboard"), "GET /api/admin/dashboard")

        # --- 用户管理 ---
        print("\n📌 5. 用户管理")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/users"), "GET /api/admin/users")

        import time
        test_user = f"testuser_{int(time.time()) % 100000}"
        resp = self.client.post(f"{self.base}/api/admin/users", json={
            "username": test_user, "password": "test123", "email": "test@test.com", "role": "user"
        })
        data = self.assert_ok(resp, "POST /api/admin/users (创建用户)")

        # 通过列表获取用户 ID
        list_resp = self.client.get(f"{self.base}/api/admin/users")
        user_list = list_resp.json() if list_resp.status_code < 400 else []
        test_user_id = next((u["id"] for u in user_list if u.get("username") == test_user), None)
        if test_user_id:
            self.assert_ok(
                self.client.put(f"{self.base}/api/admin/users/{test_user_id}", json={"is_active": True}),
                f"PUT /api/admin/users/{test_user_id} (启用)"
            )

        # --- Credential 管理 ---
        print("\n📌 6. Git 凭据管理")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/credentials"), "GET /api/admin/credentials")

        resp = self.client.post(f"{self.base}/api/admin/credentials", json={
            "name": "test-github-token", "auth_type": "https",
            "username": "test-user", "password": "ghp_test123",
            "description": "测试用 Token"
        })
        data = self.assert_ok(resp, "POST /api/admin/credentials (创建凭据)")
        cred_id = data.get("id") if data else None

        # --- Repo 管理 ---
        print("\n📌 7. Git 仓库管理")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/repos"), "GET /api/admin/repos")

        resp = self.client.post(f"{self.base}/api/admin/repos", json={
            "name": "test-repo",
            "url": "https://github.com/test/test-repo.git",
            "main_branch": "main",
            "credential_id": cred_id,
            "enabled": True,
            "allow_write": False,
            "allow_push": False,
            "description": "测试仓库"
        })
        data = self.assert_ok(resp, "POST /api/admin/repos (创建仓库)")
        repo_id = data.get("id") if data else None

        self.assert_ok(
            self.client.put(f"{self.base}/api/admin/repos/{repo_id}", json={"description": "更新描述"}),
            f"PUT /api/admin/repos/{repo_id} (更新)"
        )

        # --- Access Key 管理 ---
        print("\n📌 8. Access Key 管理")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/keys"), "GET /api/admin/keys")

        resp = self.client.post(f"{self.base}/api/admin/keys", json={
            "description": "测试 Key", "enabled": True
        })
        data = self.assert_ok(resp, "POST /api/admin/keys (创建 Key)")
        key_id = data.get("id") if data else None
        access_key = data.get("ak") if data else None
        if access_key:
            print(f"   新 Key: {access_key[:20]}...")

        # --- 权限分配 ---
        print("\n📌 9. 权限分配")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/permissions"), "GET /api/admin/permissions")

        resp = self.client.post(f"{self.base}/api/admin/permissions", json={
            "key_id": key_id, "repo_id": repo_id,
            "access_level": "read_only",
            "branch_pattern": ".*", "path_pattern": ".*"
        })
        data = self.assert_ok(resp, "POST /api/admin/permissions (授权)")
        perm_id = data.get("id") if data else None

        # --- IP 白名单 ---
        print("\n📌 10. IP 白名单")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/whitelist/{key_id}"), f"GET /api/admin/whitelist/{key_id}")

        self.assert_ok(
            self.client.post(f"{self.base}/api/admin/whitelist", json={
                "key_id": key_id,
                "entries": [
                    {"cidr": "192.168.1.0/24", "description": "办公网络"},
                    {"cidr": "127.0.0.1/32", "description": "本地测试"},
                ]
            }),
            "POST /api/admin/whitelist (设置白名单)"
        )

        # --- 审计日志 ---
        print("\n📌 11. 审计日志")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/audit-logs?limit=10"), "GET /api/admin/audit-logs")

        # --- 系统日志 ---
        print("\n📌 12. 系统日志")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/system-logs?limit=10"), "GET /api/admin/system-logs")

        # --- LLM 配置 ---
        print("\n📌 13. 大模型配置")
        self.assert_ok(self.client.get(f"{self.base}/api/admin/llm-configs"), "GET /api/admin/llm-configs")

        self.assert_ok(
            self.client.put(f"{self.base}/api/admin/llm-configs/3", json={
                "base_url": "https://api.deepseek.com",
                "model_name": "deepseek-coder",
                "api_key": "sk-test-key"
            }),
            "PUT /api/admin/llm-configs/3 (更新 DeepSeek)"
        )

        self.assert_ok(
            self.client.post(f"{self.base}/api/admin/llm-configs/3/activate"),
            "POST /api/admin/llm-configs/3/activate"
        )

        self.assert_ok(self.client.get(f"{self.base}/api/admin/llm-logs?limit=5"), "GET /api/admin/llm-logs")

        # --- MCP 端点 ---
        print("\n📌 14. MCP 协议端点")

        # 不带 Key 应被拒绝
        resp = self.client.post(f"{self.base}/mcp/query", json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/list"
        })
        assert resp.status_code in (400, 401), f"Expected 400/401, got {resp.status_code}"
        print(f"  ✅ 无 Key 被拒绝 (status={resp.status_code})")

        # 带 Key 应返回工具列表
        if access_key:
            resp = self.client.post(f"{self.base}/mcp/query", headers={
                "X-Access-Key": access_key
            }, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/list"
            })
            data = self.assert_ok(resp, "POST /mcp/query (tools/list)")
            if data and "result" in data:
                tools = data["result"].get("tools", [])
                print(f"   MCP 工具数: {len(tools)}")
                if tools:
                    for t in tools:
                        print(f"     - {t.get('name', '?')}")

        # --- 清理 ---
        print("\n📌 15. 清理测试数据")
        if perm_id:
            self.assert_ok(
                self.client.delete(f"{self.base}/api/admin/permissions/{perm_id}"),
                "DELETE /api/admin/permissions (撤销权限)"
            )
        if key_id:
            self.assert_ok(
                self.client.delete(f"{self.base}/api/admin/keys/{key_id}"),
                "DELETE /api/admin/keys (删除 Key)"
            )
        if repo_id:
            self.assert_ok(
                self.client.delete(f"{self.base}/api/admin/repos/{repo_id}"),
                "DELETE /api/admin/repos (删除仓库)"
            )
        if cred_id:
            self.assert_ok(
                self.client.delete(f"{self.base}/api/admin/credentials/{cred_id}"),
                "DELETE /api/admin/credentials (删除凭据)"
            )

        # --- 总结 ---
        print(f"\n{'=' * 60}")
        total = self.passed + self.failed
        print(f"测试结果: {self.passed}/{total} 通过, {self.failed} 失败")
        if self.failed == 0:
            print("🎉 全部通过！")
        else:
            print("⚠️ 有测试失败，请检查上面日志")
        print(f"{'=' * 60}")

    def close(self):
        self.client.close()


if __name__ == "__main__":
    tester = APITester()
    try:
        tester.run()
    finally:
        tester.close()
