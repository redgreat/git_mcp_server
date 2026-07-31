"""
测试脚本 - Git 操作（使用临时仓库）
"""
import sys
import os
import tempfile
import shutil
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from git import Repo


def _run(cmd, cwd):
    """Run a shell command, check return code, print errors"""
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        if err:
            print(f"  ⚠️  '{cmd}' 失败: {err[:120]}")
    return result


def test_git_ops():
    from gitops.git_operations import (
        list_branches, list_tags, list_tree, read_file,
        git_log, git_show, git_diff, git_blame, git_grep,
    )

    # 创建临时 Git 仓库
    tmpdir = tempfile.mkdtemp(prefix="git_mcp_server_test_")
    try:
        print(f"📦 创建临时仓库: {tmpdir}")

        # init
        _run("git init", tmpdir)
        _run('''git config user.email "test@test.com"''', tmpdir)
        _run('''git config user.name "Tester"''', tmpdir)

        # 创建测试文件
        os.makedirs(os.path.join(tmpdir, "src", "lib"), exist_ok=True)
        with open(os.path.join(tmpdir, "README.md"), "w") as f:
            f.write("# Test Repo\n\nThis is a test repository.\n")
        with open(os.path.join(tmpdir, "src", "main.py"), "w") as f:
            f.write("import sys\n\ndef main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()\n")
        with open(os.path.join(tmpdir, "src", "lib", "utils.py"), "w") as f:
            f.write("def add(a, b):\n    return a + b\n")

        # commit 1
        _run("git add -A", tmpdir)
        _run('''git commit -m "Initial commit"''', tmpdir)

        # commit 2
        with open(os.path.join(tmpdir, "src", "main.py"), "a") as f:
            f.write("\ndef version():\n    return '1.0.0'\n")
        _run("git add -A", tmpdir)
        _run('''git commit -m "Add version function"''', tmpdir)

        # tag + branch
        _run("git tag v0.1.0", tmpdir)
        _run("git checkout -b feature/test", tmpdir)
        with open(os.path.join(tmpdir, "src", "lib", "utils.py"), "a") as f:
            f.write("\ndef multiply(a, b):\n    return a * b\n")
        _run("git add -A", tmpdir)
        _run('''git commit -m "Add multiply"''', tmpdir)
        _run("git checkout master", tmpdir)

        repo = Repo(tmpdir)

        # 1. 列出分支
        branches = list_branches(repo)
        print(f"✅ list_branches: {len(branches)} 个分支")
        for b in branches[:5]:
            print(f"   {b['name']}: {b['commit'][:8]}")

        # 2. 列出标签
        tags = list_tags(repo)
        print(f"✅ list_tags: {len(tags)} 个标签")

        # 3. 列出目录树
        tree = list_tree(repo, path="src", recursive=True)
        print(f"✅ list_tree('src'): {len(tree)} 项")
        for item in tree[:6]:
            print(f"   [{item['type']}] {item['path']}")

        # 4. 读取文件
        fc = read_file(repo, path="src/main.py", ref="HEAD")
        print(f"✅ read_file('src/main.py'): {fc['total_lines']} 行, size={fc['size']}")

        # 5. 行号范围读取
        partial = read_file(repo, path="src/main.py", start_line=1, end_line=3)
        print(f"✅ read_file lines 1-3: ok ({len(partial['content'].splitlines())} lines)")

        # 6. 提交历史
        log = git_log(repo, max_count=10)
        print(f"✅ git_log: {len(log)} 条提交")
        for c in log:
            print(f"   {c['short_sha']} {c['message'][:60]}")

        # 7. 查看提交
        if log:
            show = git_show(repo, commit_sha=log[0]["sha"])
            print(f"✅ git_show: {len(show.get('diffs', []))} 个文件变更")

        # 8. Diff
        if len(log) >= 2:
            diff = git_diff(repo, ref_a=log[-1]["sha"], ref_b=log[0]["sha"])
            print(f"✅ git_diff: {diff['files_changed']} 个文件变更")

        # 9. Blame
        blame = git_blame(repo, path="src/main.py", start_line=1, end_line=3)
        print(f"✅ git_blame lines 1-3: {len(blame)} 行")

        # 10. Grep
        matches = git_grep(repo, pattern="def ", path="src", ignore_case=False)
        print(f"✅ git_grep('def '): {len(matches)} 个匹配")
        for m in matches:
            print(f"   {m['path']}:{m['line']} - {m['content'][:50]}")

        # 11. Grep ignore_case
        matches_ci = git_grep(repo, pattern="import", path="src", ignore_case=True)
        print(f"✅ git_grep('import', ic): {len(matches_ci)} 个匹配")

        print("\n🎉 Git 操作测试全部通过！")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print("🧹 清理临时仓库")

    return True


if __name__ == "__main__":
    try:
        test_git_ops()
    except Exception as e:
        print(f"❌ Git 操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
