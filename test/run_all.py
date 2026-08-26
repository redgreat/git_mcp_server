"""
一键运行所有测试
用法:
  .venv/Scripts/python test/run_all.py          # 全部测试
  .venv/Scripts/python test/run_all.py --step   # 逐步测试
"""
import subprocess
import sys
import os
import time

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

STEPS = [
    ("1. 配置加载", ["test_config.py"]),
    ("2. 数据库 Schema", ["test_db.py"]),
    ("3. 认证服务", ["test_auth.py"]),
    ("4. Git 操作", ["test_git_ops.py"]),
    ("5. MCP 协议", ["test_mcp_protocol.py"]),
    ("6. API 集成测试", ["test_api.py"]),
]

def run_test(script):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    cmd = [".venv\\Scripts\\python", f"test\\{script}"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    return result.returncode == 0, result.stdout + result.stderr

def main():
    step_mode = "--step" in sys.argv

    all_pass = True

    # 启动服务器
    print(f"🚀 启动服务器...")
    import subprocess as sp
    sp.run("pkill -f src.server", shell=True, capture_output=True)
    time.sleep(1)
    sp.Popen(
        [".venv/Scripts/python", "-m", "src.server"],
        stdout=sp.DEVNULL, stderr=sp.DEVNULL
    )
    time.sleep(4)

    for title, scripts in STEPS:
        print(f"\n{'=' * 60}")
        print(f"📌 {title}")
        print(f"{'=' * 60}")

        if step_mode:
            input("按 Enter 继续...")

        for script in scripts:
            ok, output = run_test(script)
            print(output)
            if not ok:
                all_pass = False
                print(f"❌ {script} 失败，继续下一个...")
                if step_mode:
                    input("按 Enter 继续...")

        time.sleep(0.5)

    print(f"\n{'=' * 60}")
    if all_pass:
        print("🎉 全部测试通过！")
    else:
        print("⚠️ 部分测试失败，请查看上面日志")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
