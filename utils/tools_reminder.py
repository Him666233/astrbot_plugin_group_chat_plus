"""
工具提醒器模块
负责提取和提醒AI当前可用的工具

作者: Him666233
版本: v1.2.1
"""

from typing import List, Dict, Optional
from astrbot.api.all import *

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class ToolsReminder:
    """
    工具提醒器

    主要功能：
    1. 获取所有可用的LLM工具
    2. 格式化工具列表为可读文本
    3. 将工具信息注入消息
    """

    @staticmethod
    def get_available_tools(context: Context) -> List[Dict]:
        """
        获取所有可用的LLM工具

        包括官方和第三方插件的工具

        Args:
            context: Context对象

        Returns:
            工具信息列表
        """
        try:
            # 获取LLM工具管理器
            tool_manager = context.get_llm_tool_manager()
            if not tool_manager:
                logger.warning("无法获取LLM工具管理器")
                return []

            # 直接访问func_list属性获取所有工具
            tools = tool_manager.func_list

            tool_list = []
            for tool in tools:
                tool_info = {
                    "name": getattr(tool, "name", "未命名工具"),
                    "description": getattr(tool, "description", "无描述"),
                    "parameters": [],
                }

                # 尝试获取参数信息
                if hasattr(tool, "parameters"):
                    try:
                        params = tool.parameters
                        if isinstance(params, dict) and "properties" in params:
                            # parameters是对象格式，提取properties
                            for param_name, param_info in params["properties"].items():
                                param_desc = {
                                    "name": param_name,
                                    "type": param_info.get("type", "unknown"),
                                    "description": param_info.get("description", ""),
                                }
                                tool_info["parameters"].append(param_desc)
                    except Exception as e:
                        logger.warning(
                            f"获取工具 {tool_info['name']} 的参数信息失败: {e}"
                        )

                tool_list.append(tool_info)

            if DEBUG_MODE:
                logger.info(f"获取到 {len(tool_list)} 个可用工具")
            return tool_list

        except Exception as e:
            logger.error(f"获取可用工具时发生错误: {e}")
            return []

    @staticmethod
    def format_tools_info(tools: List[Dict]) -> str:
        """
        格式化工具列表为可读文本

        Args:
            tools: 工具信息列表

        Returns:
            格式化后的文本
        """
        if not tools:
            return "当前没有可用的工具。"

        formatted_parts = []
        formatted_parts.append(f"当前平台共有 {len(tools)} 个可用工具:")
        formatted_parts.append("")

        for idx, tool in enumerate(tools, 1):
            formatted_parts.append(f"{idx}. 工具名称: {tool['name']}")
            formatted_parts.append(f"   功能描述: {tool['description']}")

            # 如果有参数信息,也列出来
            if tool.get("parameters"):
                formatted_parts.append("   参数:")
                for param in tool["parameters"]:
                    param_line = f"     - {param['name']} ({param['type']})"
                    if param.get("description"):
                        param_line += f": {param['description']}"
                    formatted_parts.append(param_line)

            formatted_parts.append("")  # 空行分隔

        return "\n".join(formatted_parts)

    @staticmethod
    async def get_persona_tool_names(
        context: Context, unified_msg_origin: str, platform_name: str = ""
    ) -> Optional[List[str]]:
        """
        获取当前会话人格允许使用的工具名称列表

        Args:
            context: Context对象
            unified_msg_origin: 会话的unified_msg_origin
            platform_name: 平台名称

        Returns:
            工具名称列表，None表示使用所有工具（人格未限制或旧版不支持）
        """
        try:
            # 检查是否有persona_manager和conversation_manager（兼容旧版AstrBot）
            if not hasattr(context, "persona_manager") or not hasattr(
                context, "conversation_manager"
            ):
                if DEBUG_MODE:
                    logger.info("当前AstrBot版本不支持人格工具过滤,使用全部工具")
                return None

            persona_mgr = context.persona_manager
            conv_mgr = context.conversation_manager

            if not persona_mgr or not conv_mgr:
                return None

            # 获取当前会话的conversation_id
            curr_cid = await conv_mgr.get_curr_conversation_id(unified_msg_origin)
            if not curr_cid:
                return None

            # 获取当前会话对象，提取persona_id
            conv = await conv_mgr.get_conversation(unified_msg_origin, curr_cid)
            if not conv:
                return None

            conversation_persona_id = getattr(conv, "persona_id", None)

            # 解析当前生效的人格
            persona_id, persona, _, _ = await persona_mgr.resolve_selected_persona(
                umo=unified_msg_origin,
                conversation_persona_id=conversation_persona_id,
                platform_name=platform_name,
            )

            if not persona:
                return None

            # 获取人格的tools字段
            persona_tools = persona.get("tools", None)

            if persona_tools is None:
                # None表示使用所有工具
                if DEBUG_MODE:
                    logger.info(f"人格 {persona_id} 未限制工具,使用全部工具")
                return None

            if DEBUG_MODE:
                logger.info(f"人格 {persona_id} 限制工具列表: {persona_tools}")
            return persona_tools

        except Exception as e:
            logger.warning(f"获取人格工具列表失败,回退到全部工具: {e}")
            return None

    @staticmethod
    def inject_tools_to_message(
        original_message: str,
        context: Context,
        allowed_tool_names: Optional[List[str]] = None,
    ) -> str:
        """
        将工具信息注入到消息

        Args:
            original_message: 原始消息
            context: Context对象
            allowed_tool_names: 允许的工具名称列表，None表示不过滤

        Returns:
            注入工具信息后的文本
        """
        try:
            # 获取工具列表
            tools = ToolsReminder.get_available_tools(context)

            # 按人格配置过滤工具
            if allowed_tool_names is not None:
                tools = [t for t in tools if t["name"] in allowed_tool_names]
                if DEBUG_MODE:
                    logger.info(f"按人格过滤后剩余 {len(tools)} 个工具")

            if not tools:
                if DEBUG_MODE:
                    logger.info("没有可用工具,跳过工具提醒")
                return original_message

            # 格式化工具信息
            tools_info = ToolsReminder.format_tools_info(tools)

            # 注入到消息中
            injected_message = (
                original_message + "\n\n=== 可用工具列表 ===\n" + tools_info
            )
            injected_message += (
                "\n(以上是你可以调用的所有工具,根据需要选择合适的工具使用)"
            )

            if DEBUG_MODE:
                logger.info(f"工具信息已注入,共 {len(tools)} 个工具")
            return injected_message

        except Exception as e:
            logger.error(f"注入工具信息时发生错误: {e}")
            return original_message
