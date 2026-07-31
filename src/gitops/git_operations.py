"""
Git 操作封装 - 基于 bare repo 的只读操作
"""
import re
from typing import List, Optional, Dict, Any
from git import Repo, GitCommandError
try:
    from ..logging_utils import get_logger
except ImportError:
    from logging_utils import get_logger

logger = get_logger("git_ops", "logs")


def list_branches(repo: Repo, pattern: str = None) -> List[Dict[str, Any]]:
    """列出分支"""
    branches = []
    for ref in repo.references:
        if ref.name.startswith("refs/heads/") or ref.name.startswith("refs/remotes/"):
            name = ref.name.replace("refs/heads/", "").replace("refs/remotes/origin/", "")
            if pattern and not re.search(pattern, name):
                continue
            branches.append({
                "name": name,
                "commit": str(ref.commit.hexsha),
                "is_remote": ref.name.startswith("refs/remotes/"),
            })
    return branches


def list_tags(repo: Repo) -> List[Dict[str, str]]:
    """列出标签"""
    tags = []
    for tag in repo.tags:
        try:
            commit_sha = str(tag.commit.hexsha)
        except Exception:
            commit_sha = "unknown"
        tags.append({
            "name": tag.name,
            "commit": commit_sha,
        })
    return sorted(tags, key=lambda t: t["name"])


def list_tree(repo: Repo, path: str = "", ref: str = "HEAD",
              recursive: bool = True) -> List[Dict[str, Any]]:
    """列出目录树"""
    try:
        commit = repo.commit(ref)
        tree = commit.tree
        if path:
            tree = tree / path

        items = []
        for item in tree:
            if recursive and item.type == "tree":
                # 递归列出子目录
                sub_items = list_tree(repo, f"{path}/{item.name}" if path else item.name,
                                      ref, recursive=True)
                items.extend(sub_items)
            items.append({
                "name": item.name,
                "type": item.type,  # "blob" or "tree"
                "path": f"{path}/{item.name}" if path else item.name,
                "size": item.size if hasattr(item, "size") else None,
            })
        return items
    except GitCommandError as e:
        raise RuntimeError(f"列出目录树失败: {e}")


def read_file(repo: Repo, path: str, ref: str = "HEAD",
              start_line: int = None, end_line: int = None) -> Dict[str, Any]:
    """读取文件内容"""
    try:
        commit = repo.commit(ref)
        blob = commit.tree / path

        content = blob.data_stream.read().decode("utf-8", errors="replace")
        total_lines = content.count("\n") + 1

        # 行号过滤
        if start_line is not None or end_line is not None:
            lines = content.split("\n")
            sl = max(1, (start_line or 1)) - 1
            el = min(len(lines), (end_line or len(lines)))
            lines = lines[sl:el]
            content = "\n".join(lines)

        return {
            "path": path,
            "ref": ref,
            "content": content,
            "total_lines": total_lines,
            "size": blob.size,
            "commit_sha": str(commit.hexsha),
            "commit_date": str(commit.committed_datetime),
            "commit_author": str(commit.author),
        }
    except KeyError:
        raise RuntimeError(f"文件不存在: {path} @ {ref}")
    except GitCommandError as e:
        raise RuntimeError(f"读取文件失败: {e}")


def git_log(repo: Repo, ref: str = "HEAD", path: str = None,
            max_count: int = 50, since: str = None, until: str = None) -> List[Dict[str, Any]]:
    """获取提交历史"""
    try:
        kwargs = {"max_count": min(max_count, 200)}
        if path:
            kwargs["paths"] = path
        if since:
            kwargs["since"] = f"{since}T00:00:00"
        if until:
            kwargs["until"] = f"{until}T23:59:59"

        commits = list(repo.iter_commits(ref, **kwargs))
        result = []
        for c in commits:
            result.append({
                "sha": str(c.hexsha),
                "short_sha": str(c.hexsha)[:8],
                "author": str(c.author),
                "date": str(c.committed_datetime),
                "message": c.message.strip(),
                "parents": [str(p.hexsha) for p in c.parents],
            })
        return result
    except GitCommandError as e:
        raise RuntimeError(f"获取提交历史失败: {e}")


def git_show(repo: Repo, commit_sha: str) -> Dict[str, Any]:
    """查看某次提交的详细信息"""
    try:
        commit = repo.commit(commit_sha)

        diffs = []
        if commit.parents:
            parent = commit.parents[0]
            diff_index = parent.diff(commit, create_patch=True)
        else:
            diff_index = commit.diff(None, create_patch=True)

        for d in diff_index:
            diffs.append({
                "change_type": d.change_type,  # A/D/M/R
                "old_path": d.a_path,
                "new_path": d.b_path,
                "diff": d.diff.decode("utf-8", errors="replace") if d.diff else "",
            })

        return {
            "sha": str(commit.hexsha),
            "author": str(commit.author),
            "date": str(commit.committed_datetime),
            "message": commit.message.strip(),
            "parents": [str(p.hexsha) for p in commit.parents],
            "stats": commit.stats.total if commit.stats else {},
            "diffs": diffs,
        }
    except GitCommandError as e:
        raise RuntimeError(f"查看提交失败: {e}")


def git_diff(repo: Repo, ref_a: str, ref_b: str, path: str = None) -> Dict[str, Any]:
    """比较两个版本的差异"""
    try:
        commit_a = repo.commit(ref_a)
        commit_b = repo.commit(ref_b)

        kwargs = {"create_patch": True}
        if path:
            kwargs["paths"] = [path]

        diff_index = commit_a.diff(commit_b, **kwargs)

        diffs = []
        for d in diff_index:
            diffs.append({
                "change_type": d.change_type,
                "old_path": d.a_path,
                "new_path": d.b_path,
                "diff": d.diff.decode("utf-8", errors="replace") if d.diff else "",
            })

        return {
            "ref_a": ref_a,
            "ref_b": ref_b,
            "files_changed": len(diffs),
            "diffs": diffs,
        }
    except GitCommandError as e:
        raise RuntimeError(f"比较差异失败: {e}")


def git_blame(repo: Repo, path: str, ref: str = "HEAD",
              start_line: int = None, end_line: int = None) -> List[Dict[str, Any]]:
    """查看文件每行的修改信息"""
    try:
        commit = repo.commit(ref)

        # 使用 git blame
        blame_result = repo.git.blame("-p", ref, "--", path)

        lines = []
        current_commit = {}
        for line in blame_result.split("\n"):
            if line.startswith("\t"):
                # 源代码行
                current_commit["content"] = line[1:]
                lines.append(dict(current_commit))
                current_commit = {}
            elif " " in line and line.split(" ", 1)[0].isalnum():
                parts = line.split(" ", 1)
                sha = parts[0]
                current_commit = {
                    "sha": sha,
                    "short_sha": sha[:8],
                    "content": "",
                }
            elif line.startswith("author "):
                current_commit["author"] = line[7:]
            elif line.startswith("author-time "):
                current_commit["author_time"] = line[12:]
            elif line.startswith("summary "):
                current_commit["summary"] = line[8:]

        # 行号过滤
        if start_line is not None or end_line is not None:
            sl = max(0, (start_line or 1) - 1)
            el = min(len(lines), (end_line or len(lines)))
            lines = lines[sl:el]

        # 添加行号
        for i, line in enumerate(lines):
            line["line_number"] = (start_line or 1) + i

        return lines
    except GitCommandError as e:
        raise RuntimeError(f"Blame 失败: {e}")


def git_grep(repo: Repo, pattern: str, path: str = None,
             ref: str = "HEAD", ignore_case: bool = False) -> List[Dict[str, Any]]:
    """代码搜索"""
    try:
        args = ["-n"]  # 显示行号
        if ignore_case:
            args.append("-i")

        # 使用 git grep
        cmd_args = args + [pattern, ref]
        if path:
            cmd_args.extend(["--", path])

        result = repo.git.grep(*cmd_args)
        if not result:
            return []

        # git grep -n output: "path:lineno:content"
        # Parse from right to left to handle paths with colons
        import re
        matches = []
        for line in result.split("\n"):
            if not line.strip():
                continue
            # Find the last colon that separates line number from content
            # Pattern: path:number:content
            m = re.match(r'^(.+?):(\d+):(.*)$', line)
            if m:
                matches.append({
                    "path": m.group(1),
                    "line": int(m.group(2)),
                    "content": m.group(3),
                })

        return matches
    except GitCommandError as e:
        if "exit code" in str(e) and "1" in str(e):
            return []  # grep 没找到结果
        raise RuntimeError(f"代码搜索失败: {e}")
