"""
表情包检测器模块
负责检测消息中的图片是否为平台标记的表情包（贴纸/Sticker）

检测原理：
- NapCat/OneBot 协议中，图片消息的 sub_type 字段可以区分普通图片和表情包
  * sub_type=0: 普通图片
  * sub_type=1: 表情包/贴纸
- QQ 平台中，表情包图片的 summary 字段通常包含"表情"关键词

检测优先级：
1. 从原始事件消息段（raw_message.message）中提取 image segments，检查 sub_type
2. 检查 summary 字段是否包含 "表情"/"emoji"/"sticker"
3. 检查 Image 组件对象的 subType / sub_type 属性
4. 通过 toDict() 获取完整数据检查

作者: Him666233
版本: v1.2.1
"""

from typing import List, Optional
from astrbot.api import logger

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False

# 表情包标记常量
EMOJI_MARKER = "[表情包图片]"
# 表情包内联提示（附加在标记后，帮助多模态AI正确理解图片类型）
EMOJI_INLINE_HINT = (
    "（系统提示：用户发送的图片是一张表情包/贴纸，不是普通照片或截图。"
    "你可以看懂图片来理解其传达的情绪和幽默感，"
    '但请像真人一样自然回应——不要描述或复述图片内容，不要说"你发了个表情包"。）'
)


class EmojiDetector:
    """
    表情包检测器

    主要功能：
    1. 检测消息中的图片是否为平台标记的表情包
    2. 为表情包消息添加标记，供 AI 识别
    """

    @staticmethod
    def _normalize_str(value: object) -> str:
        """标准化字符串值，处理 None、反引号包裹等情况"""
        if value is None:
            return ""
        try:
            s = str(value)
        except Exception:
            return ""
        s = s.strip()
        if s.startswith("`") and s.endswith("`") and len(s) >= 2:
            s = s[1:-1].strip()
        return s

    @staticmethod
    def _is_sub_type_emoji(sub_type: object) -> bool:
        """判断 sub_type 值是否表示表情包（sub_type=1 为表情包）"""
        if sub_type is None:
            return False
        if sub_type == 1 or sub_type == "1":
            return True
        try:
            return int(sub_type) == 1
        except Exception:
            return False

    @staticmethod
    def _is_emoji_summary(summary: object) -> bool:
        """判断 summary 字段是否包含表情包关键词"""
        s = EmojiDetector._normalize_str(summary)
        if not s:
            return False
        s_lower = s.lower()
        return "表情" in s or "emoji" in s_lower or "sticker" in s_lower

    @staticmethod
    def is_emoji_message(event) -> bool:
        """
        检测消息中是否包含平台标记的表情包

        通过多层检测方式判断消息中的图片是否为表情包/贴纸，
        任一图片被识别为表情包即返回 True。

        Args:
            event: AstrMessageEvent 消息事件对象

        Returns:
            bool: 消息中是否包含表情包图片
        """
        try:
            # 确保事件对象有消息链
            if not hasattr(event, "message_obj"):
                return False

            message_obj = event.message_obj
            if not hasattr(message_obj, "message") or not message_obj.message:
                return False

            # 导入 Image 类型（延迟导入避免循环依赖）
            from astrbot.core.message.components import Image

            # 检查消息链中是否有图片组件
            image_components = [
                comp for comp in message_obj.message if isinstance(comp, Image)
            ]
            if not image_components:
                return False

            # === 方式0：从原始事件消息中提取 image segments（最可靠） ===
            raw_image_segments = []
            try:
                raw_message = getattr(message_obj, "raw_message", None)
                raw_msg_list = getattr(raw_message, "message", None)
                if isinstance(raw_msg_list, list):
                    raw_image_segments = [
                        seg
                        for seg in raw_msg_list
                        if isinstance(seg, dict) and seg.get("type") == "image"
                    ]
            except Exception:
                raw_image_segments = []

            # 如果有原始 image segments，优先检查
            if raw_image_segments:
                for seg in raw_image_segments:
                    if not isinstance(seg, dict):
                        continue
                    data = seg.get("data", {}) or {}
                    if not isinstance(data, dict):
                        continue

                    # 检查 sub_type
                    sub_type = data.get("sub_type") or data.get("subType")
                    if EmojiDetector._is_sub_type_emoji(sub_type):
                        if DEBUG_MODE:
                            logger.info(
                                f"[表情包检测] 检测到表情包: sub_type={sub_type} (原始事件)"
                            )
                        return True

                    # 检查 summary
                    summary = data.get("summary", "")
                    if EmojiDetector._is_emoji_summary(summary):
                        if DEBUG_MODE:
                            logger.info(
                                f"[表情包检测] 检测到表情包: summary='{summary}' (原始事件)"
                            )
                        return True

            # === 方式1：检查 Image 组件的属性 ===
            for img in image_components:
                # 检查 subType 属性
                if hasattr(img, "subType") and img.subType is not None:
                    if EmojiDetector._is_sub_type_emoji(img.subType):
                        if DEBUG_MODE:
                            logger.info(
                                f"[表情包检测] 检测到表情包: subType={img.subType} (组件属性)"
                            )
                        return True

                # 检查 __dict__ 中的 sub_type
                if hasattr(img, "__dict__"):
                    sub_type = img.__dict__.get("sub_type")
                    if EmojiDetector._is_sub_type_emoji(sub_type):
                        if DEBUG_MODE:
                            logger.info(
                                f"[表情包检测] 检测到表情包: sub_type={sub_type} (组件__dict__)"
                            )
                        return True

                # === 方式2：通过 toDict() 检查 ===
                try:
                    raw_data = img.toDict()
                    if isinstance(raw_data, dict) and "data" in raw_data:
                        data = raw_data["data"]
                        if isinstance(data, dict):
                            sub_type = data.get("sub_type") or data.get("subType")
                            if EmojiDetector._is_sub_type_emoji(sub_type):
                                if DEBUG_MODE:
                                    logger.info(
                                        f"[表情包检测] 检测到表情包: sub_type={sub_type} (toDict)"
                                    )
                                return True

                            summary = data.get("summary", "")
                            if EmojiDetector._is_emoji_summary(summary):
                                if DEBUG_MODE:
                                    logger.info(
                                        f"[表情包检测] 检测到表情包: summary='{summary}' (toDict)"
                                    )
                                return True

                            # 检查 type 字段
                            img_type = (
                                data.get("type")
                                or data.get("imageType")
                                or data.get("image_type")
                            )
                            if img_type in ("emoji", "sticker", "face", "meme"):
                                if DEBUG_MODE:
                                    logger.info(
                                        f"[表情包检测] 检测到表情包: type='{img_type}' (toDict)"
                                    )
                                return True
                except Exception:
                    pass

            return False

        except Exception as e:
            if DEBUG_MODE:
                logger.warning(f"[表情包检测] 检测失败: {e}")
            return False

    @staticmethod
    def add_emoji_marker(message_text: str) -> str:
        """
        为消息文本添加表情包标记

        在消息文本的最前面添加 [表情包图片] 标记，
        让 AI 知道这条消息中的图片是表情包而非普通照片。

        Args:
            message_text: 原始消息文本

        Returns:
            添加标记后的消息文本
        """
        if not message_text:
            return f"{EMOJI_MARKER}{EMOJI_INLINE_HINT}"

        # 如果已经有标记了，不重复添加
        if EMOJI_MARKER in message_text:
            return message_text

        return f"{EMOJI_MARKER}{EMOJI_INLINE_HINT} {message_text}"
