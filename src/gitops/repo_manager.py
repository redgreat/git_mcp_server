"""
Git 仓库管理器 - 管理本地 bare repo 缓存
"""
import os
import re
import time
import threading
from typing import Optional, Dict, List
from dataclasses import dataclass
from urllib.parse import quote

from git import Repo, GitCommandError
try:
    from ..config import GitStorageConfig
    from ..logging_utils import get_logger
except ImportError:
    from config import GitStorageConfig
    from logging_utils import get_logger


@dataclass
class RepoInfo:
    """本地仓库缓存信息"""
    repo_id: int
    repo_url: str
    repo_name: str
    bare_path: str
    last_access: float
    last_fetch: float


class GitRepoManager:
    """Git Bare Repo 缓存管理器

    在本地磁盘维护 bare repo 缓存：
    - 首次访问时 clone --bare
    - 之后访问时检查是否需要 fetch
    - 定期清理长期未访问的仓库
    """

    def __init__(self, cfg: GitStorageConfig):
        self.cfg = cfg
        self.base_dir = cfg.base_dir
        self.cache_ttl = cfg.cache_ttl
        self.fetch_interval = cfg.fetch_interval
        self._cache: Dict[int, RepoInfo] = {}
        self._lock = threading.Lock()
        self.logger = get_logger("git_repo_manager", "logs")

        os.makedirs(self.base_dir, exist_ok=True)
        self._start_cleanup_loop()

    def _repo_path(self, repo_name: str) -> str:
        """获取仓库的本地存储路径"""
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', repo_name)
        return os.path.join(self.base_dir, f"{safe_name}.git")

    def get_repo(self, repo_id: int, repo_name: str, repo_url: str,
                 username: str = None, password: str = None) -> Repo:
        """获取仓库对象（首次 clone，之后复用）

        Args:
            repo_id: 仓库 ID
            repo_name: 仓库名称
            repo_url: Git clone 地址
            username: 认证用户名（可选）
            password: 认证密码/Token（可选）

        Returns:
            git.Repo 对象
        """
        bare_path = self._repo_path(repo_name)

        with self._lock:
            now = time.time()

            # 检查缓存
            if repo_id in self._cache:
                info = self._cache[repo_id]
                info.last_access = now

                # 是否需要 fetch
                if now - info.last_fetch > self.fetch_interval:
                    self.logger.info(f"自动 fetch: {repo_name} (间隔 {int(now - info.last_fetch)}s)")
                    self._do_fetch(info, username, password)

                return Repo(bare_path)

            # 首次 clone 或重新加载
            if os.path.exists(bare_path):
                self.logger.info(f"加载已有仓库: {repo_name} at {bare_path}")
                repo = Repo(bare_path)
                # 更新 remote URL
                self._update_remote(repo, repo_url, username, password)
                self._do_fetch_raw(repo, bare_path, username, password)
            else:
                self.logger.info(f"首次克隆仓库: {repo_name} from {repo_url} (depth=1)")
                repo = self._clone_bare(repo_url, bare_path, username, password)

            info = RepoInfo(
                repo_id=repo_id,
                repo_url=repo_url,
                repo_name=repo_name,
                bare_path=bare_path,
                last_access=now,
                last_fetch=now,
            )
            self._cache[repo_id] = info
            return repo

    def _clone_bare(self, url: str, path: str,
                    username: str = None, password: str = None) -> Repo:
        """Clone --bare 到本地

        使用浅克隆 (depth=1) 加速首次拉取，不带 blob:none 过滤，
        确保文件内容一并下载，MCP 工具可直接读取。
        """
        auth_url = self._inject_auth(url, username, password)
        try:
            repo = Repo.clone_from(
                auth_url, path,
                bare=True,
                depth=1,  # 浅克隆，加速首次拉取
            )
            return repo
        except GitCommandError as e:
            # 如果浅克隆失败（老 Git），尝试完整 clone
            self.logger.warning(f"浅克隆失败，尝试完整克隆: {e}")
            try:
                repo = Repo.clone_from(auth_url, path, bare=True)
                return repo
            except GitCommandError as e2:
                raise RuntimeError(f"克隆仓库失败: {e2}")

    def _do_fetch(self, info: RepoInfo, username: str = None, password: str = None):
        """执行 fetch 更新"""
        repo = Repo(info.bare_path)
        self._do_fetch_raw(repo, info.bare_path, username, password)
        info.last_fetch = time.time()

    def _do_fetch_raw(self, repo: Repo, bare_path: str,
                      username: str = None, password: str = None):
        """执行底层 fetch"""
        try:
            # 获取所有 remote
            for remote in repo.remotes:
                auth_url = self._inject_auth(remote.url, username, password)
                remote.set_url(auth_url)
                # 浅克隆 (depth=1) 可能缺失 fetch refspec，补齐后 fetch 才能找到引用
                try:
                    has_refspec = bool(repo.git.config('--get', f'remote.{remote.name}.fetch'))
                except GitCommandError:
                    has_refspec = False
                if not has_refspec:
                    repo.git.config('--replace-all', f'remote.{remote.name}.fetch',
                                    '+refs/heads/*:refs/remotes/origin/*')
            fetched = repo.remotes.origin.fetch(prune=True, tags=True)
            updated = [
                f for f in fetched
                if f.flags & (f.FAST_FORWARD | f.NEW_HEAD | f.FORCED_UPDATE)
            ]
            self.logger.info(f"Fetch 完成: {bare_path}, {len(fetched)} refs, {len(updated)} 更新")
            for f in updated:
                change = "new" if f.flags & f.NEW_HEAD else ("fast-forward" if f.flags & f.FAST_FORWARD else "forced-update")
                self.logger.info(f"  {f.ref}: {f.old_commit} -> {f.commit} ({change})")
        except GitCommandError as e:
            self.logger.error(f"Fetch 失败 {bare_path}: {e}")

    def _update_remote(self, repo: Repo, url: str,
                       username: str = None, password: str = None):
        """更新 remote URL"""
        auth_url = self._inject_auth(url, username, password)
        if repo.remotes:
            origin = repo.remotes.origin
            if origin.url != auth_url:
                origin.set_url(auth_url)

    def _inject_auth(self, url: str, username: str = None, password: str = None) -> str:
        """将用户名密码注入 HTTPS URL，对特殊字符进行 URL 编码"""
        if not username or not password:
            return url
        if url.startswith("https://"):
            prefix = "https://"
            rest = url[len(prefix):]
            encoded_username = quote(username, safe='')
            encoded_password = quote(password, safe='')
            return f"{prefix}{encoded_username}:{encoded_password}@{rest}"
        return url

    def force_fetch(self, repo_id: int, username: str = None, password: str = None):
        """强制 fetch 最新代码"""
        with self._lock:
            info = self._cache.get(repo_id)
            if info:
                self._do_fetch(info, username, password)

    def fetch_and_report(self, repo_id: int, username: str = None, password: str = None) -> dict:
        """强制 fetch 并返回结果统计（供管理后台手动拉取使用）

        Returns:
            {
                "fetched": int, "updated": int, "error": str|None,
                "details": [{"ref": str, "old_commit": str, "new_commit": str, "change_type": str}]
            }
        """
        with self._lock:
            info = self._cache.get(repo_id)
            if not info:
                return {"fetched": 0, "updated": 0, "error": "仓库尚未克隆，请先通过 MCP 工具访问一次", "details": []}
            try:
                repo = Repo(info.bare_path)
                for remote in repo.remotes:
                    auth_url = self._inject_auth(remote.url, username, password)
                    remote.set_url(auth_url)
                    # 浅克隆 (depth=1) 可能缺失 fetch refspec，补齐后 fetch 才能找到引用
                    try:
                        has_refspec = bool(repo.git.config('--get', f'remote.{remote.name}.fetch'))
                    except GitCommandError:
                        has_refspec = False
                    if not has_refspec:
                        repo.git.config('--replace-all', f'remote.{remote.name}.fetch',
                                        '+refs/heads/*:refs/remotes/origin/*')
                fetched = repo.remotes.origin.fetch(prune=True, tags=True)
                info.last_fetch = time.time()
                updated = [
                    f for f in fetched
                    if f.flags & (f.FAST_FORWARD | f.NEW_HEAD | f.FORCED_UPDATE)
                ]
                # 构建详细的更新信息
                details = []
                for f in updated:
                    change_type = "new" if f.flags & f.NEW_HEAD else ("fast-forward" if f.flags & f.FAST_FORWARD else "forced-update")
                    details.append({
                        "ref": f.ref,
                        "old_commit": str(f.old_commit.hexsha)[:8] if f.old_commit else None,
                        "new_commit": str(f.commit.hexsha)[:8] if f.commit else None,
                        "change_type": change_type,
                    })
                self.logger.info(f"手动拉取完成: {info.repo_name}, {len(fetched)} refs, {len(updated)} 更新")
                if details:
                    for d in details:
                        self.logger.info(f"  {d['ref']}: {d['old_commit']} -> {d['new_commit']} ({d['change_type']})")
                return {"fetched": len(fetched), "updated": len(updated), "error": None, "details": details}
            except GitCommandError as e:
                self.logger.error(f"手动拉取失败 {info.bare_path}: {e}")
                return {"fetched": 0, "updated": 0, "error": str(e), "details": []}

    def remove_repo(self, repo_id: int):
        """从缓存中移除仓库（不删除磁盘文件）"""
        with self._lock:
            self._cache.pop(repo_id, None)

    def cleanup(self):
        """清理长期未访问的仓库缓存"""
        with self._lock:
            now = time.time()
            expired = [
                rid for rid, info in self._cache.items()
                if now - info.last_access > self.cache_ttl
            ]
            for rid in expired:
                self.logger.info(f"清理过期缓存: {self._cache[rid].repo_name}")
                self._cache.pop(rid, None)

    def _start_cleanup_loop(self):
        """启动定期清理任务"""
        def cleanup_loop():
            while True:
                time.sleep(self.cache_ttl // 2)
                self.cleanup()

        t = threading.Thread(target=cleanup_loop, daemon=True)
        t.start()

    def get_repo_status(self, repo_id: int) -> Optional[dict]:
        """获取仓库缓存状态"""
        with self._lock:
            info = self._cache.get(repo_id)
            if not info:
                return None
            return {
                "repo_id": info.repo_id,
                "repo_name": info.repo_name,
                "bare_path": info.bare_path,
                "last_access": info.last_access,
                "last_fetch": info.last_fetch,
            }
