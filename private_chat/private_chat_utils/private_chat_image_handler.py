"""
私信图片处理器模块
负责处理私信消息中的图片，包括检测、多模态传递和图片转文字

与群聊版本的区别：
1. 无 scope/at/keyword 过滤逻辑（私信每条都处理）
2. 功能关闭或无 provider 时：图片直接传递（多模态模式），而非过滤丢弃
3. 省钱缓存命中不计入 AI 调用限制计数，只有实际 AI 调用才计数

作者: Him666233
版本: v1.2.1
"""

import asyncio
from typing import List, Optional, Tuple
from astrbot.api.all import *
from astrbot.api.message_components import Face, At, Reply
from .private_chat_image_description_cache import ImageDescriptionCache

# 详细日志开关
DEBUG_MODE: bool = False


class ImageHandler:
    """
    私信图片处理器

    主要功能：
    1. 检测消息中的图片（支持单图/多图）
    2. 多模态模式：提取图片URL直接传递给AI
    3. 图片转文字模式：调用AI将图片转为文字描述（含省钱缓存）
    4. 串行处理多张图片，缓存命中不计入AI调用限制
    """

    @staticmethod
    async def process_message_images(
        event: AstrMessageEvent,
        context: Context,
        enable_image_processing: bool,
        image_to_text_provider_id: str,
        image_to_text_prompt: str,
        timeout: int = 60,
        image_description_cache: Optional[ImageDescriptionCache] = None,
        max_images_per_message: int = 10,
    ) -> Tuple[bool, str, List[str], bool]:
        """
        处理私信消息中的图片

        与群聊版本的关键区别：
        - 无 scope/at/keyword 过滤（私信场景下每条消息都处理）
        - 功能关闭时不丢弃图片，而是直接传递（多模态模式）

        Args:
            event: 消息事件
            context: Context对象
            enable_image_processing: 是否启用图片处理（图片转文字）
            image_to_text_provider_id: 图片转文字AI提供商ID（留空=多模态直传）
            image_to_text_prompt: 转换提示词
            timeout: 图片转文字超时时间（秒）
            image_description_cache: 图片描述缓存实例（与群聊共享，可选）
            max_images_per_message: 单条消息最大处理图片数

        Returns:
            (是否继续处理, 处理后的消息, 图片URL列表, 图片是否保留)
            - True=继续，False=丢弃
            - 图片URL列表：用于多模态AI直接处理
            - 图片是否保留：True=图片信息仍在消息中（作为URL或文字描述）
        """
        try:
            # 获取消息链
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return True, event.get_message_outline(), [], False

            message_chain = event.message_obj.message

            # 检查消息中是否有图片
            has_image, has_text, image_components = ImageHandler._analyze_message(
                message_chain, max_images_per_message
            )

            # 如果没有图片，从消息链提取完整文本（含引用内容）
            if not has_image:
                text_content = ImageHandler._extract_text_only(message_chain)
                if not text_content:
                    text_content = event.get_message_outline()
                return True, text_content, [], False

            if DEBUG_MODE:
                logger.info(
                    f"[私信图片处理] 检测到消息包含 {len(image_components)} 张图片, "
                    f"是否有文字: {has_text}"
                )

            # === 私信图片处理逻辑 ===
            # 与群聊不同：功能关闭或无provider时，图片直接传递（多模态模式）

            # 情况1：图片处理功能关闭 → 多模态直传
            if not enable_image_processing:
                if DEBUG_MODE:
                    logger.info(
                        "[私信图片处理] 图片处理未启用，图片直接传递（多模态模式）"
                    )
                image_urls = await ImageHandler._extract_image_urls(image_components)
                text_content = ImageHandler._extract_text_only(message_chain)
                return True, text_content, image_urls, True

            # 情况2：功能开启但未配置provider → 多模态直传
            if not image_to_text_provider_id:
                if DEBUG_MODE:
                    logger.info(
                        "[私信图片处理] 未配置图片转文字提供商ID，图片直接传递（多模态模式）"
                    )
                image_urls = await ImageHandler._extract_image_urls(image_components)
                text_content = ImageHandler._extract_text_only(message_chain)
                return True, text_content, image_urls, True

            # 情况3：功能开启且有provider → 图片转文字（含省钱缓存）
            if DEBUG_MODE:
                logger.info(
                    f"[私信图片处理] 开始图片转文字，provider={image_to_text_provider_id}，"
                    f"超时={timeout}秒，图片数={len(image_components)}"
                )

            processed_message = await ImageHandler._convert_images_to_text(
                message_chain,
                context,
                image_to_text_provider_id,
                image_to_text_prompt,
                image_components,
                timeout,
                image_description_cache,
                max_images_per_message,
            )

            # 转换失败的降级处理
            if processed_message is None:
                logger.warning("[私信图片处理] 图片转文字失败，使用占位符降级")
                if not has_text:
                    # 纯图片消息转换失败：用占位符替代
                    fallback_parts = []
                    for comp in message_chain:
                        if isinstance(comp, Image):
                            fallback_parts.append("[图片（识别失败）]")
                        else:
                            fmt = ImageHandler._format_special_component(comp)
                            if fmt:
                                fallback_parts.append(fmt)
                    fallback_text = (
                        "".join(fallback_parts).strip() or "[图片（识别失败）]"
                    )
                    return True, fallback_text, [], False
                else:
                    # 图文混合消息转换失败：保留文字
                    text_only = ImageHandler._extract_text_only(message_chain)
                    return True, text_only, [], False

            # 转换成功
            if DEBUG_MODE:
                logger.info(f"[私信图片处理] 图片转文字成功: {processed_message[:150]}")
            return True, processed_message, [], True

        except Exception as e:
            logger.error(f"[私信图片处理] 处理消息图片时发生错误: {e}")
            return True, event.get_message_outline(), [], False

    @staticmethod
    def _analyze_message(
        message_chain: List[BaseMessageComponent],
        max_images: int = 10,
    ) -> Tuple[bool, bool, List[Image]]:
        """
        分析消息链，检查图片和文字

        Args:
            message_chain: 消息链
            max_images: 单条消息最大处理图片数

        Returns:
            (是否有图片, 是否有文字, 图片组件列表)
        """
        has_image = False
        has_text = False
        image_components = []

        for component in message_chain:
            if isinstance(component, Image):
                has_image = True
                image_components.append(component)
            elif isinstance(component, Plain):
                if component.text and component.text.strip():
                    has_text = True
            elif isinstance(component, Reply):
                has_text = True

        # 限制单条消息处理的图片数量
        if len(image_components) > max_images:
            logger.warning(
                f"[私信图片处理] 单条消息包含 {len(image_components)} 张图片，"
                f"超过上限 {max_images}，仅处理前 {max_images} 张"
            )
            image_components = image_components[:max_images]

        return has_image, has_text, image_components

    @staticmethod
    def _format_special_component(component: BaseMessageComponent) -> str:
        """
        格式化特殊消息组件为文本表示

        Args:
            component: 消息组件

        Returns:
            格式化后的文本，如果不是特殊组件返回空字符串
        """
        if isinstance(component, Face):
            return f"[表情:{component.id}]"
        elif isinstance(component, At):
            return f"[At:{component.qq}]"
        elif isinstance(component, Reply):
            try:
                message_content = getattr(component, "message_str", None) or getattr(
                    component, "message", None
                )
                sender_nickname = getattr(
                    component, "sender_nickname", None
                ) or getattr(component, "sender_name", None)
                if not sender_nickname and hasattr(component, "sender"):
                    sender_nickname = getattr(component.sender, "nickname", None)
                sender_id = getattr(component, "sender_id", None)
                if message_content:
                    if sender_nickname and sender_id:
                        return f"[引用 {sender_nickname}(ID:{sender_id}): {message_content}]"
                    elif sender_id:
                        return f"[引用 用户(ID:{sender_id}): {message_content}]"
                    elif sender_nickname:
                        return f"[引用 {sender_nickname}: {message_content}]"
                    else:
                        return f"[引用消息: {message_content}]"
                return "[引用消息]"
            except Exception:
                return "[引用消息]"
        else:
            return ""

    @staticmethod
    def _extract_text_only(message_chain: List[BaseMessageComponent]) -> str:
        """
        从消息链提取纯文字，过滤图片

        Args:
            message_chain: 消息链

        Returns:
            纯文字内容
        """
        text_parts = []

        for component in message_chain:
            if isinstance(component, Plain):
                text_parts.append(component.text)
            elif isinstance(component, Image):
                continue
            else:
                formatted = ImageHandler._format_special_component(component)
                if formatted:
                    text_parts.append(formatted)

        result = "".join(text_parts).strip()
        if not result:
            logger.warning(
                f"[私信图片处理] _extract_text_only 提取到空文本！"
                f"text_parts={text_parts[:5]}"
            )
        return result

    @staticmethod
    async def _extract_image_urls(image_components: List[Image]) -> List[str]:
        """
        从图片组件列表中提取图片URL

        Args:
            image_components: 图片组件列表

        Returns:
            图片URL列表
        """
        image_urls = []
        for idx, img_component in enumerate(image_components):
            try:
                image_path = await img_component.convert_to_file_path()
                if image_path:
                    image_urls.append(image_path)
                    if DEBUG_MODE:
                        logger.info(f"[私信图片处理] 提取到图片 {idx}: {image_path}")
                else:
                    logger.warning(f"[私信图片处理] 无法提取图片 {idx} 的路径")
            except Exception as e:
                logger.error(f"[私信图片处理] 提取图片 {idx} 的URL时发生错误: {e}")
                continue

        return image_urls

    @staticmethod
    async def _convert_images_to_text(
        message_chain: List[BaseMessageComponent],
        context: Context,
        provider_id: str,
        prompt: str,
        image_components: List[Image],
        timeout: int = 60,
        image_description_cache: Optional[ImageDescriptionCache] = None,
        max_ai_calls: int = 10,
    ) -> Optional[str]:
        """
        将图片转换为文字描述（含省钱缓存 + AI调用限制）

        串行处理流程：
        1. 逐张图片按顺序处理
        2. 先查缓存 → 命中直接用（不计入AI调用限制）
        3. 未命中 → 检查AI调用计数是否达到上限
           - 未达上限：调用AI转换，计数+1
           - 已达上限：使用占位符 [图片]
        4. 保存AI转换结果到缓存

        Args:
            message_chain: 消息链
            context: Context对象
            provider_id: AI提供商ID
            prompt: 转换提示词
            image_components: 图片组件列表
            timeout: 超时时间（秒）
            image_description_cache: 图片描述缓存实例（可选）
            max_ai_calls: AI调用次数上限（缓存命中不计数）

        Returns:
            转换后的文本，失败返回None
        """
        try:
            # 获取指定的提供商
            provider = context.get_provider_by_id(provider_id)
            if not provider:
                logger.error(f"[私信图片处理] 无法找到提供商: {provider_id}")
                return None

            # 建立 message_chain 中 Image 组件位置到 image_components 索引的映射
            image_chain_to_idx = {}
            img_count = 0
            for chain_idx, component in enumerate(message_chain):
                if isinstance(component, Image):
                    image_chain_to_idx[chain_idx] = img_count
                    img_count += 1

            # 串行处理每张图片
            image_descriptions = {}
            ai_call_count = 0  # AI 实际调用计数器（缓存命中不计数）

            for idx, img_component in enumerate(image_components):
                try:
                    # 获取图片URL或路径
                    image_path = await img_component.convert_to_file_path()
                    if not image_path:
                        logger.warning(f"[私信图片处理] 无法获取图片 {idx} 的路径")
                        continue

                    if DEBUG_MODE:
                        logger.info(
                            f"[私信图片处理] 处理图片 {idx}/{len(image_components)}: "
                            f"{image_path}"
                        )

                    # === 省钱逻辑：先检查缓存 ===
                    if image_description_cache and image_description_cache.enabled:
                        cached_desc = image_description_cache.lookup(image_path)
                        if cached_desc:
                            image_descriptions[idx] = cached_desc
                            logger.info(
                                f"[私信图片缓存] 图片 {idx} 命中缓存，跳过AI调用 (省钱!)"
                            )
                            continue  # 缓存命中：不计入 AI 调用计数

                    # === AI 调用限制检查 ===
                    if ai_call_count >= max_ai_calls:
                        logger.warning(
                            f"[私信图片处理] AI调用次数已达上限 {max_ai_calls}，"
                            f"图片 {idx} 使用占位符"
                        )
                        # 不写入 image_descriptions，后面构建消息时会用 [图片] 占位
                        continue

                    # === 调用AI进行图片转文字 ===
                    async def call_vision_ai():
                        response = await provider.text_chat(
                            prompt=prompt,
                            contexts=[],
                            image_urls=[image_path],
                            func_tool=None,
                            system_prompt="",
                        )
                        return response.completion_text

                    description = await asyncio.wait_for(
                        call_vision_ai(), timeout=timeout
                    )

                    if description:
                        image_descriptions[idx] = description
                        ai_call_count += 1  # 只有实际 AI 调用才计数

                        if DEBUG_MODE:
                            logger.info(
                                f"[私信图片处理] 图片 {idx} 转换成功 "
                                f"(AI调用 {ai_call_count}/{max_ai_calls}): "
                                f"{description[:50]}..."
                            )

                        # 保存到缓存
                        if image_description_cache and image_description_cache.enabled:
                            if not image_description_cache.lookup(image_path):
                                image_description_cache.save(image_path, description)

                except asyncio.TimeoutError:
                    logger.warning(
                        f"[私信图片处理] 图片 {idx} 转文字超时（超过 {timeout} 秒）"
                    )
                    ai_call_count += 1  # 超时也计入 AI 调用计数（消耗了时间）
                    continue
                except Exception as e:
                    logger.error(f"[私信图片处理] 转换图片 {idx} 时发生错误: {e}")
                    continue

            # 如果没有成功转换任何图片，返回 None
            if not image_descriptions:
                logger.warning("[私信图片处理] 没有成功转换任何图片")
                return None

            # 构建新的消息文本，将图片替换为描述或占位符
            result_parts = []
            for chain_idx, component in enumerate(message_chain):
                if isinstance(component, Plain):
                    result_parts.append(component.text)
                elif isinstance(component, Image):
                    if chain_idx in image_chain_to_idx:
                        img_idx = image_chain_to_idx[chain_idx]
                        if img_idx in image_descriptions:
                            result_parts.append(
                                f"[图片内容: {image_descriptions[img_idx]}]"
                            )
                        else:
                            result_parts.append("[图片]")
                    else:
                        result_parts.append("[图片]")
                else:
                    formatted = ImageHandler._format_special_component(component)
                    if formatted:
                        result_parts.append(formatted)

            result_text = "".join(result_parts)
            if DEBUG_MODE:
                logger.info(f"[私信图片处理] 图片转文字完成: {result_text[:100]}...")
            return result_text

        except Exception as e:
            logger.error(f"[私信图片处理] 图片转文字过程发生错误: {e}")
            return None
