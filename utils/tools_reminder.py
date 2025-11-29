"""
工具提醒器模块
负责提取和提醒AI当前可用的工具

作者: Him666233
版本: v1.1.2
"""

from typing import List, Dict
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
    def inject_tools_to_message(original_message: str, context: Context) -> str:
        """
        将工具信息注入到消息

        Args:
            original_message: 原始消息
            context: Context对象

        Returns:
            注入工具信息后的文本
        """
        try:
            # 获取工具列表
            tools = ToolsReminder.get_available_tools(context)

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
