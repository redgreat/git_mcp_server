"""
Git 仓库管理器 - 管理本地 bare repo 缓存
"""
import os
import re
import stat
import tempfile
import time
import threading
from typing import Optional, Dict, List, Tuple
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
        # 将仓库基目录加入 Git safe.directory，避免 dubious ownership 错误
        self._ensure_safe_directory(self.base_dir)
        self._start_cleanup_loop()

    _safe_directory_tmpcfg = None  # 类级别的临时配置文件路径，避免重复创建

    @classmethod
    def _ensure_safe_directory(cls, path: str):
        """将目录加入 Git safe.directory 配置，防止 dubious ownership 错误

        依次尝试：
        1. git config --global --add（常规情况）
        2. git config --system --add（Docker 容器中 $HOME 不可写时）
        3. GIT_CONFIG_GLOBAL 临时文件（以上都失败时，所有仓库共用一个临时文件）
        """
        import subprocess
        try:
            # 尝试 1: 全局配置
            result = subprocess.run(
                ['git', 'config', '--global', '--add', 'safe.directory', path],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return

            # 尝试 2: 系统配置
            result = subprocess.run(
                ['git', 'config', '--system', '--add', 'safe.directory', path],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return

            # 尝试 3: 临时全局配置文件（复用已有的临时文件）
            if cls._safe_directory_tmpcfg and os.path.exists(cls._safe_directory_tmpcfg):
                tmp_path = cls._safe_directory_tmpcfg
            else:
                fd, tmp_path = tempfile.mkstemp(suffix='.gitconfig', prefix='git-safe-')
                os.close(fd)
                cls._safe_directory_tmpcfg = tmp_path

            try:
                subprocess.run(
                    ['git', 'config', '--file', tmp_path, '--add', 'safe.directory', path],
                    capture_output=True, timeout=10
                )
                os.environ['GIT_CONFIG_GLOBAL'] = tmp_path
            except Exception:
                pass
        except Exception:
            pass  # 忽略错误（如 git 不存在等）

    def _repo_path(self, repo_id: int, repo_name: str) -> str:
        """获取仓库的本地存储路径；仓库 ID 防止中文名称清洗后发生碰撞。"""
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', repo_name)
        return os.path.join(self.base_dir, f"{repo_id}_{safe_name}.git")

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
        bare_path = self._repo_path(repo_id, repo_name)

        with self._lock:
            now = time.time()

            # 检查缓存
            if repo_id in self._cache:
                info = self._cache[repo_id]
                info.last_access = now

                self._ensure_safe_directory(bare_path)
                repo = Repo(bare_path)
                self._fixup_refs(repo, bare_path)

                # 是否需要 fetch
                if not list(repo.references) or now - info.last_fetch > self.fetch_interval:
                    self.logger.info(f"自动 fetch: {repo_name} (间隔 {int(now - info.last_fetch)}s)")
                    self._do_fetch(info, username, password)

                return Repo(bare_path)

            # 首次 clone 或重新加载
            if os.path.exists(bare_path):
                self.logger.info(f"加载已有仓库: {repo_name} at {bare_path}")
                # 确保已有仓库也在 safe.directory 中
                self._ensure_safe_directory(bare_path)
                repo = Repo(bare_path)
                # 修复 refs（兼容旧版 --bare 克隆的仓库）
                self._fixup_refs(repo, bare_path)
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
        """克隆仓库到本地

        使用浅克隆 (depth=1) + no_checkout 策略：
        - 下载 commit 历史 + 文件内容（blob），但不检出工作目录
        - HEAD 正确指向默认分支，远程跟踪分支自动创建
        - 解决 --bare 克隆导致 HEAD/refs 缺失、工具无法读取的问题
        凭据通过 GIT_ASKPASS 机制传递，避免特殊字符导致 URL 解析失败。
        """
        askpass_path = None
        old_env = {}
        try:
            # 如果有凭据，设置 ASKPASS 环境变量
            if username and password:
                askpass_path, askpass_env = self._create_askpass(username, password)
                for k, v in askpass_env.items():
                    old_env[k] = os.environ.get(k)
                    os.environ[k] = v

            # 使用不带凭据的 URL（凭据由 ASKPASS 提供）
            try:
                repo = Repo.clone_from(
                    url, path,
                    no_checkout=True,  # 不检出工作目录，节省空间
                    depth=1,           # 浅克隆，加速首次拉取
                )
                # 克隆后立即加入 safe.directory，防止 dubious ownership
                self._ensure_safe_directory(path)
                # 确保 HEAD 指向有效的远程跟踪分支
                self._fixup_refs(repo, path)
                return repo
            except GitCommandError as e:
                # 如果浅克隆失败（老 Git），尝试完整 clone
                self.logger.warning(f"浅克隆失败，尝试完整克隆: {e}")
                try:
                    repo = Repo.clone_from(url, path, no_checkout=True)
                    self._ensure_safe_directory(path)
                    self._fixup_refs(repo, path)
                    return repo
                except GitCommandError as e2:
                    raise RuntimeError(f"克隆仓库失败: {e2}")
        finally:
            # 恢复环境变量
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            # 清理临时脚本
            self._cleanup_askpass(askpass_path)

    @staticmethod
    def _fixup_refs(repo: Repo, path: str):
        """修复克隆后的 refs，确保 HEAD 指向有效的远程跟踪分支"""
        try:
            # 查找远程跟踪分支
            remote_heads = [ref for ref in repo.references
                           if ref.name.startswith('refs/remotes/origin/')
                          and not ref.name.endswith('/HEAD')]
            if not remote_heads and repo.remotes:
                # 兼容旧的 bare/镜像缓存：远端分支可能直接落在 refs/heads。
                local_heads = [ref for ref in repo.references if ref.name.startswith('refs/heads/')]
                if local_heads:
                    try:
                        repo.git.symbolic_ref('HEAD', local_heads[0].name)
                    except GitCommandError:
                        pass
                    return
            if remote_heads:
                # 设置 HEAD 指向第一个远程跟踪分支
                default_ref = remote_heads[0]
                try:
                    repo.git.symbolic-ref('HEAD', default_ref.name)
                except GitCommandError:
                    pass
                # 同时创建本地分支引用（方便 log/blame 等工具）
                for ref in remote_heads:
                    branch_name = ref.name.replace('refs/remotes/origin/', '')
                    try:
                        repo.git.update-ref(
                            f'refs/heads/{branch_name}',
                            ref.commit.hexsha
                        )
                    except GitCommandError:
                        pass
            elif not repo.references:
                # 完全没有任何引用，创建空 HEAD
                try:
                    repo.git.symbolic-ref('HEAD', 'refs/heads/main')
                except GitCommandError:
                    pass
        except Exception:
            pass  # 忽略所有错误，不影响核心功能

    def _do_fetch(self, info: RepoInfo, username: str = None, password: str = None):
        """执行 fetch 更新"""
        repo = Repo(info.bare_path)
        self._do_fetch_raw(repo, info.bare_path, username, password)
        info.last_fetch = time.time()

    def _do_fetch_raw(self, repo: Repo, bare_path: str,
                      username: str = None, password: str = None):
        """执行底层 fetch

        凭据通过 GIT_ASKPASS 机制传递，避免特殊字符导致 URL 解析失败。
        """
        askpass_path = None
        old_env = {}
        try:
            # 如果有凭据，设置 ASKPASS 环境变量
            if username and password:
                askpass_path, askpass_env = self._create_askpass(username, password)
                for k, v in askpass_env.items():
                    old_env[k] = os.environ.get(k)
                    os.environ[k] = v

            # 获取所有 remote，使用不带凭据的 URL
            for remote in repo.remotes:
                # 去除 URL 中的凭据部分（如果有），改用 ASKPASS
                clean_url = self._strip_auth_from_url(remote.url)
                remote.set_url(clean_url)
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
            # fetch 后修复 refs，确保新分支可被工具访问
            self._fixup_refs(repo, bare_path)
        except GitCommandError as e:
            self.logger.error(f"Fetch 失败 {bare_path}: {e}")
        finally:
            # 恢复环境变量
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            # 清理临时脚本
            self._cleanup_askpass(askpass_path)

    def _update_remote(self, repo: Repo, url: str,
                       username: str = None, password: str = None):
        """更新 remote URL（不带凭据，凭据由 ASKPASS 提供）"""
        clean_url = self._strip_auth_from_url(url)
        if repo.remotes:
            origin = repo.remotes.origin
            if origin.url != clean_url:
                origin.set_url(clean_url)

    @staticmethod
    def _strip_auth_from_url(url: str) -> str:
        """去除 URL 中的 user:pass@ 部分"""
        if '@' in url and '://' in url:
            prefix, rest = url.split('://', 1)
            if '@' in rest:
                _, host_part = rest.rsplit('@', 1)
                return f"{prefix}://{host_part}"
        return url

    def _create_askpass(self, username: str, password: str) -> Tuple[str, dict]:
        """创建 GIT_ASKPASS 脚本，避免凭据嵌入 URL 导致特殊字符解析失败

        Returns:
            (askpass_script_path, env_dict)
        """
        fd, askpass_path = tempfile.mkstemp(suffix='.sh', prefix='git-askpass-')
        try:
            # ASKPASS 脚本：根据提示返回用户名或密码
            script = (
                '#!/bin/sh\n'
                'if echo "$1" | grep -qi "Username"; then\n'
                f'  echo "{username}"\n'
                'else\n'
                f'  echo "{password}"\n'
                'fi\n'
            )
            with os.fdopen(fd, 'w') as f:
                f.write(script)
            os.chmod(askpass_path, stat.S_IRWXU)

            env = {
                'GIT_ASKPASS': askpass_path,
                'GIT_TERMINAL_PROMPT': '0',  # 禁用交互式提示
                'SSH_ASKPASS': askpass_path,
            }
            self.logger.info(f"创建 ASKPASS 脚本: {askpass_path}")
            return askpass_path, env
        except Exception:
            # 创建失败时清理临时文件
            try:
                os.unlink(askpass_path)
            except OSError:
                pass
            raise

    def _cleanup_askpass(self, askpass_path: str):
        """清理临时 ASKPASS 脚本"""
        if askpass_path and os.path.exists(askpass_path):
            try:
                os.unlink(askpass_path)
                self.logger.info(f"清理 ASKPASS 脚本: {askpass_path}")
            except OSError:
                pass

    def _inject_auth(self, url: str, username: str = None, password: str = None) -> str:
        """将用户名密码注入 HTTPS URL，对特殊字符进行 URL 编码

        注意：当用户名包含 @ 等字符时，URL 编码可能导致 libcurl 解析失败。
        此时应使用 _create_askpass() 代替此方法。
        """
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
        askpass_path = None
        old_env = {}
        try:
            with self._lock:
                info = self._cache.get(repo_id)
                if not info:
                    return {"fetched": 0, "updated": 0, "error": "仓库尚未克隆，请先通过 MCP 工具访问一次", "details": []}

                # 如果有凭据，设置 ASKPASS 环境变量
                if username and password:
                    askpass_path, askpass_env = self._create_askpass(username, password)
                    for k, v in askpass_env.items():
                        old_env[k] = os.environ.get(k)
                        os.environ[k] = v

                try:
                    repo = Repo(info.bare_path)
                    for remote in repo.remotes:
                        # 去除 URL 中的凭据部分，改用 ASKPASS
                        clean_url = self._strip_auth_from_url(remote.url)
                        remote.set_url(clean_url)
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
        finally:
            # 恢复环境变量
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            # 清理临时脚本
            self._cleanup_askpass(askpass_path)

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
