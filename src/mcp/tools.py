"""
MCP 工具定义
"""
from typing import Dict, Any


class MCPTool:
    """MCP 工具定义"""

    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


MCP_TOOLS = [
    # ---- 仓库浏览 ----
    MCPTool(
        name="list_repos",
        description="列出当前 Access Key 有权访问的 Git 仓库列表",
        input_schema={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "可选搜索关键词，匹配仓库名称或描述"
                }
            }
        }
    ),
    MCPTool(
        name="list_branches",
        description="列出指定仓库的所有分支",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "pattern": {"type": "string", "description": "可选，分支名过滤正则"}
            },
            "required": ["repo_id"]
        }
    ),
    MCPTool(
        name="list_tags",
        description="列出指定仓库的所有标签",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
            },
            "required": ["repo_id"]
        }
    ),

    # ---- 文件浏览 ----
    MCPTool(
        name="list_tree",
        description="列出指定仓库的目录树（支持指定路径和分支）",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "path": {"type": "string", "description": "目录路径，默认为根目录"},
                "ref": {"type": "string", "description": "分支名/标签名/commit SHA，默认 HEAD"},
                "recursive": {"type": "boolean", "description": "是否递归列出，默认 true"},
            },
            "required": ["repo_id"]
        }
    ),
    MCPTool(
        name="read_file",
        description="读取仓库中指定文件的内容（支持指定版本）",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "path": {"type": "string", "description": "文件路径"},
                "ref": {"type": "string", "description": "分支名/标签名/commit SHA，默认 HEAD"},
                "start_line": {"type": "integer", "description": "起始行号（可选）"},
                "end_line": {"type": "integer", "description": "结束行号（可选）"},
            },
            "required": ["repo_id", "path"]
        }
    ),

    # ---- 版本历史 ----
    MCPTool(
        name="git_log",
        description="查看仓库的提交历史",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "ref": {"type": "string", "description": "分支名/标签名，默认 HEAD"},
                "path": {"type": "string", "description": "可选，仅查看特定文件的提交历史"},
                "max_count": {"type": "integer", "description": "最多返回条数，默认 50"},
                "since": {"type": "string", "description": "起始日期，格式 YYYY-MM-DD"},
                "until": {"type": "string", "description": "截止日期，格式 YYYY-MM-DD"},
            },
            "required": ["repo_id"]
        }
    ),
    MCPTool(
        name="git_show",
        description="查看某次提交的详细信息（包含 diff）",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "commit_sha": {"type": "string", "description": "commit SHA"},
            },
            "required": ["repo_id", "commit_sha"]
        }
    ),
    MCPTool(
        name="git_diff",
        description="比较两个版本之间的差异",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "ref_a": {"type": "string", "description": "版本A（分支/标签/commit）"},
                "ref_b": {"type": "string", "description": "版本B（分支/标签/commit）"},
                "path": {"type": "string", "description": "可选，仅比较特定路径"},
            },
            "required": ["repo_id", "ref_a", "ref_b"]
        }
    ),
    MCPTool(
        name="git_blame",
        description="查看文件每行的最后修改者和提交信息",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "path": {"type": "string", "description": "文件路径"},
                "ref": {"type": "string", "description": "分支名/标签名/commit SHA，默认 HEAD"},
                "start_line": {"type": "integer", "description": "起始行号"},
                "end_line": {"type": "integer", "description": "结束行号"},
            },
            "required": ["repo_id", "path"]
        }
    ),

    # ---- 代码搜索 ----
    MCPTool(
        name="git_grep",
        description="在仓库中搜索代码（支持正则表达式）",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "pattern": {"type": "string", "description": "搜索正则表达式"},
                "path": {"type": "string", "description": "可选，限定搜索路径"},
                "ref": {"type": "string", "description": "分支名/标签名，默认 HEAD"},
                "ignore_case": {"type": "boolean", "description": "是否忽略大小写，默认 false"},
            },
            "required": ["repo_id", "pattern"]
        }
    ),

    # ---- AI 分析 ----
    MCPTool(
        name="analyze_code",
        description="使用大模型分析指定代码文件的逻辑",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "path": {"type": "string", "description": "文件路径"},
                "ref": {"type": "string", "description": "分支名/标签名/commit SHA，默认 HEAD"},
                "question": {"type": "string", "description": "要询问的问题（如：这段代码的逻辑是什么？）"},
            },
            "required": ["repo_id", "path", "question"]
        }
    ),
    MCPTool(
        name="review_diff",
        description="使用大模型审查两个版本的代码差异",
        input_schema={
            "type": "object",
            "properties": {
                "repo_id": {"type": "integer", "description": "仓库 ID"},
                "ref_a": {"type": "string", "description": "版本A"},
                "ref_b": {"type": "string", "description": "版本B"},
                "path": {"type": "string", "description": "可选，限定路径"},
            },
            "required": ["repo_id", "ref_a", "ref_b"]
        }
    ),
]
