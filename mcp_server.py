"""
NeuroMemory MCP Server

基于 Anthropic Model Context Protocol (MCP) 的服务端实现。
提供三个 tools：
- process_memory: 生产模式，返回结构化 JSON
- debug_process_memory: 调试模式，返回自然语言报告
- get_user_graph: 获取用户知识图谱

启动方式（stdio 模式）：
    python -m mcp_server

或者在 Claude Desktop / Cursor 配置中添加。
"""
import json
import logging
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
    stream=sys.stderr,  # MCP 使用 stdout 通信，日志输出到 stderr
)
logger = logging.getLogger("neuro_memory.mcp")

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    logger.error("MCP SDK 未安装，请运行: pip install mcp")
    sys.exit(1)

from private_brain import get_brain
from session_manager import get_session_manager

# 创建 MCP Server 实例
server = Server("neuro-memory")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的 tools"""
    return [
        Tool(
            name="process_memory",
            description="""处理用户输入，检索相关记忆并异步存储（v3.0）。
            
返回结构化 JSON，包含：
- resolved_query: 指代消解后的查询
- memories: 语义相关的记忆片段
- relations: 知识图谱中的关系
- metadata: 检索耗时、是否有记忆等信息

适用于：将记忆上下文注入到 LLM prompt 中""",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "用户输入文本（刺激）",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "用户标识，用于隔离不同用户的记忆",
                    },
                },
                "required": ["input", "user_id"],
            },
        ),
        Tool(
            name="debug_process_memory",
            description="""调试模式：处理用户输入并返回详细的处理过程。
            
返回自然语言格式的报告，包含：
- 检索过程（向量匹配结果、图谱关系）
- 存储决策（隐私分类结果、是否存储）
- 性能统计（各阶段耗时）
- 原始数据

适用于：开发调试、验证系统行为""",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "用户输入文本",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "用户标识",
                    },
                },
                "required": ["input", "user_id"],
            },
        ),
        Tool(
            name="get_user_graph",
            description="""获取用户的完整知识图谱。
            
返回用户存储的所有记忆和实体关系。

适用于：查看用户记忆状态、调试图谱结构""",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户标识",
                    },
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="end_session",
            description="""显式结束用户的当前会话。
            
后台触发长期记忆整合流程，将短期记忆整合为长期记忆。

注意：接口立即返回，整合过程在后台异步执行。""",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户标识",
                    },
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="get_session_status",
            description="""获取用户当前会话状态（调试用）。
            
返回 Session 的事件数、创建时间、最后活跃时间等信息。""",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户标识",
                    },
                },
                "required": ["user_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理 tool 调用"""
    logger.info(f"Tool 调用: {name}, 参数: {arguments}")
    
    brain = get_brain()
    
    try:
        if name == "process_memory":
            input_text = arguments.get("input", "")
            user_id = arguments.get("user_id", "default_user")
            
            result = await brain.process_async(input_text, user_id)
            return [TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )]
            
        elif name == "debug_process_memory":
            input_text = arguments.get("input", "")
            user_id = arguments.get("user_id", "default_user")
            
            result = brain.process_debug(input_text, user_id)
            return [TextContent(
                type="text",
                text=result,
            )]
            
        elif name == "get_user_graph":
            user_id = arguments.get("user_id", "default_user")
            
            result = brain.get_user_graph(user_id)
            return [TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )]
            
        elif name == "end_session":
            user_id = arguments.get("user_id", "default_user")
            
            result = await brain.end_session_async(user_id)
            return [TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )]
            
        elif name == "get_session_status":
            user_id = arguments.get("user_id", "default_user")
            
            from session_manager import get_session_manager
            session_manager = get_session_manager()
            status = session_manager.get_session_status(user_id)
            
            if status is None:
                result = {
                    "status": "success",
                    "has_active_session": False,
                    "session_info": None,
                }
            else:
                result = {
                    "status": "success",
                    "has_active_session": True,
                    "session_info": status,
                }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )]
            
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"未知的 tool: {name}"}, ensure_ascii=False),
            )]
            
    except Exception as e:
        logger.error(f"Tool 执行失败: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "error": str(e),
            }, ensure_ascii=False),
        )]


async def main():
    """启动 MCP Server（stdio 模式）"""
    logger.info("启动 NeuroMemory MCP Server (stdio 模式)")
    async with stdio_server() as (read_stream, write_stream):
        get_session_manager().start_timeout_checker()
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
