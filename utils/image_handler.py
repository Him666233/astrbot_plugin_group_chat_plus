"""
图片处理器模块
负责处理消息中的图片，包括检测、过滤和转文字

作者: Him666233
版本: v1.2.1
"""

import asyncio
from typing import List, Optional, Tuple
from astrbot.api.all import *
from astrbot.api.message_components import Face, At, Reply
from .image_description_cache import ImageDescriptionCache

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class ImageHandler:
    """
    图片处理器

    主要功能：
    1. 检测消息中的图片
    2. 过滤纯图片消息或移除图片
    3. 调用AI将图片转为文字描述
    4. 将描述融入原消息
    """

    @staticmethod
    async def process_message_images(
        event: AstrMessageEvent,
        context: Context,
        enable_image_processing: bool,
        image_to_text_scope: str,
        image_to_text_provider_id: str,
        image_to_text_prompt: str,
        is_at_message: bool,
        has_trigger_keyword: bool,
        timeout: int = 60,
        image_description_cache: Optional[ImageDescriptionCache] = None,
        max_images_per_message: int = 10,
    ) -> Tuple[bool, str, List[str], bool]:
        """
        处理消息中的图片

        Args:
            event: 消息事件
            context: Context对象
            enable_image_processing: 是否启用图片处理
            image_to_text_scope: 应用范围（all/mention_only/at_only/keyword_only）
            image_to_text_provider_id: 图片转文字AI提供商ID
            image_to_text_prompt: 转换提示词
            is_at_message: 是否@消息
            has_trigger_keyword: 是否包含触发关键词
            timeout: 图片转文字超时时间（秒）
            image_description_cache: 图片描述缓存实例（可选，用于省钱）
            max_images_per_message: 单条消息最大处理图片数

        Returns:
            (是否继续处理, 处理后的消息, 图片URL列表, 图片是否保留)
            - True=继续，False=丢弃
            - 图片URL列表：用于多模态AI直接处理
            - 图片是否保留：True=图片信息仍在消息中（作为URL或文字描述），False=图片已被移除/过滤
        """
        try:
            # 获取消息链
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                # 没有消息链,使用原始文本
                return True, event.get_message_outline(), [], False

            message_chain = event.message_obj.message

            # 检查消息中是否有图片
            has_image, has_text, image_components = ImageHandler._analyze_message(
                message_chain, max_images_per_message
            )

            # 如果没有图片，从消息链提取完整文本（含引用内容），不使用 get_message_outline()
            # 因为 get_message_outline() 通常不包含引用消息（Reply 组件）的内容
            if not has_image:
                text_content = ImageHandler._extract_text_only(message_chain)
                if not text_content:
                    # 兜底：message chain 提取为空时才使用 get_message_outline()
                    text_content = event.get_message_outline()
                return True, text_content, [], False

            if DEBUG_MODE:
                logger.info(
                    f"检测到消息包含 {len(image_components)} 张图片, 是否有文字: {has_text}"
                )

            # === 第一步：检查图片处理开关 ===
            # 如果不启用图片处理，所有带图片的消息都要过滤（不管是什么模式）
            if not enable_image_processing:
                if DEBUG_MODE:
                    logger.info("图片处理未启用,过滤所有图片")
                # 如果是纯图片消息,丢弃
                if not has_text:
                    if DEBUG_MODE:
                        logger.info("检测到纯图片消息,但图片处理未启用,丢弃该消息")
                    return False, "", [], False
                else:
                    # 如果是图文混合,移除图片只保留文字
                    text_only = ImageHandler._extract_text_only(message_chain)
                    if DEBUG_MODE:
                        logger.info(f"移除图片后的消息: {text_only}")
                    return True, text_only, [], False

            # === 第二步：根据应用范围(image_to_text_scope)决定是否对当前消息启用图片转文字 ===
            scope = (image_to_text_scope or "all").strip().lower()
            should_apply_image_to_text = True

            # 🔍 调试日志：始终输出scope判断信息，便于排查问题
            logger.info(
                f"🖼️ [图片范围检查] scope={scope}, is_at_message={is_at_message}, has_trigger_keyword={has_trigger_keyword}"
            )

            if scope == "all":
                should_apply_image_to_text = True
            elif scope == "mention_only":
                # 兼容旧逻辑：@消息或包含触发关键词的消息都视为适用
                should_apply_image_to_text = is_at_message or has_trigger_keyword
            elif scope == "at_only":
                # 仅对真正的@机器人消息启用图片转文字
                should_apply_image_to_text = is_at_message
            elif scope == "keyword_only":
                # 仅对包含触发关键词的消息启用图片转文字
                should_apply_image_to_text = has_trigger_keyword
            else:
                # 未知配置值时，退回到与mention_only一致的行为
                should_apply_image_to_text = is_at_message or has_trigger_keyword

            # 🔍 调试日志：输出最终判断结果
            logger.info(
                f"🖼️ [图片范围判断] should_apply_image_to_text={should_apply_image_to_text}"
            )

            if not should_apply_image_to_text:
                if DEBUG_MODE:
                    logger.info(
                        f"图片转文字应用范围为{scope}, 当前消息不符合范围, 过滤图片"
                    )
                # 如果是纯图片消息,丢弃
                if not has_text:
                    if DEBUG_MODE:
                        logger.info("非适用范围内的纯图片消息,丢弃该消息")
                    return False, "", [], False
                else:
                    # 如果是图文混合,移除图片只保留文字
                    text_only = ImageHandler._extract_text_only(message_chain)
                    if DEBUG_MODE:
                        logger.info(
                            f"非适用范围内的图文混合,移除图片保留文字: {text_only}"
                        )
                    return True, text_only, [], False

            # === 第三步：启用了图片处理，根据是否配置图片转文字ID决定处理方式 ===
            if DEBUG_MODE:
                logger.info("图片处理已启用")

            # 如果没有填写图片转文字的提供商ID,说明使用多模态AI,提取图片URL传递
            if not image_to_text_provider_id:
                if DEBUG_MODE:
                    logger.info("未配置图片转文字提供商ID,提取图片URL传递给多模态AI")
                # 提取图片URL
                image_urls = await ImageHandler._extract_image_urls(image_components)
                # 提取文本内容（不包含图片）
                text_content = ImageHandler._extract_text_only(message_chain)
                if DEBUG_MODE:
                    logger.info(
                        f"🟢 [多模态模式] 提取到 {len(image_urls)} 张图片，文本内容: {text_content[:100] if text_content else '(无文本)'}"
                    )
                return True, text_content, image_urls, True  # 多模态: 图片保留为URL

            # === 第四步：配置了图片转文字提供商ID，尝试转换图片 ===
            if DEBUG_MODE:
                logger.info(
                    f"已配置图片转文字提供商ID,尝试转换图片(超时时间: {timeout}秒)"
                )
            processed_message = await ImageHandler._convert_images_to_text(
                message_chain,
                context,
                image_to_text_provider_id,
                image_to_text_prompt,
                image_components,
                timeout,
                image_description_cache,
            )

            # 如果转换失败或超时,进行降级处理（过滤图片）
            if processed_message is None:
                logger.warning("图片转文字超时或失败,进行过滤处理")
                # 纯图片（无文字、无引用）且转换失败：不丢弃，用占位符替代每张图片
                # 仅在用户填写了转换服务商ID（真实转换模式）时才会走到这里
                if not has_text:
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
                    logger.warning(
                        f"纯图片消息转换失败，使用占位文字替代: {fallback_text}"
                    )
                    return True, fallback_text, [], False
                else:
                    # 如果是图文混合,只保留文字
                    text_only = ImageHandler._extract_text_only(message_chain)
                    if DEBUG_MODE:
                        logger.info(f"降级处理: 移除图片,保留文字: {text_only}")
                    return True, text_only, [], False  # 图片转文字失败，图片被移除

            # 转换成功，返回转换后的消息（图片已转成文字描述）
            if DEBUG_MODE:
                logger.info(f"🔴 [图片转文字成功] 结果: {processed_message[:150]}")
            return (
                True,
                processed_message,
                [],
                True,
            )  # 图片转文字成功: 图片信息保留为文字描述

        except Exception as e:
            logger.error(f"处理消息图片时发生错误: {e}")
            # 发生错误时,返回原消息文本
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
                # 检查是否有非空白文字
                if component.text and component.text.strip():
                    has_text = True
            elif isinstance(component, Reply):
                # 引用消息也视为有文字内容，防止「引用+图片」的消息被当作纯图片丢弃
                has_text = True

        # 限制单条消息处理的图片数量，防止恶意刷图
        if len(image_components) > max_images:
            logger.warning(
                f"[图片处理] 单条消息包含 {len(image_components)} 张图片，"
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
            # 格式化引用消息，保留引用内容让AI理解上下文
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
                # 跳过图片
                continue
            else:
                # 其他类型的组件,尝试转为文本表示
                formatted = ImageHandler._format_special_component(component)
                if formatted:
                    text_parts.append(formatted)

        result = "".join(text_parts).strip()
        if not result:
            logger.warning(
                f"[图片处理] _extract_text_only 提取到空文本！text_parts={text_parts[:5]}"
            )
        return result

    @staticmethod
    async def _extract_image_urls(image_components: List[Image]) -> List[str]:
        """
        从图片组件列表中提取图片URL

        Args:
            image_components: 图片组件列表

        Returns:
            图片URL列表（可能包含本地路径或base64等格式）
        """
        image_urls = []
        for idx, img_component in enumerate(image_components):
            try:
                # 尝试获取图片路径或URL
                image_path = await img_component.convert_to_file_path()
                if image_path:
                    image_urls.append(image_path)
                    if DEBUG_MODE:
                        logger.info(f"提取到图片 {idx}: {image_path}")
                else:
                    logger.warning(f"无法提取图片 {idx} 的路径")
            except Exception as e:
                logger.error(f"提取图片 {idx} 的URL时发生错误: {e}")
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
    ) -> Optional[str]:
        """
        将图片转换为文字描述

        Args:
            message_chain: 消息链
            context: Context对象
            provider_id: AI提供商ID
            prompt: 转换提示词
            image_components: 图片组件列表
            timeout: 超时时间（秒）
            image_description_cache: 图片描述缓存实例（可选）

        Returns:
            转换后的文本，失败返回None
        """
        try:
            # 获取指定的提供商
            provider = context.get_provider_by_id(provider_id)
            if not provider:
                logger.error(f"无法找到提供商: {provider_id}")
                return None

            # 建立message_chain中Image组件位置到image_components索引的映射
            # 这样可以避免使用id()，更稳定可靠
            image_chain_to_idx = {}
            img_count = 0
            for chain_idx, component in enumerate(message_chain):
                if isinstance(component, Image):
                    image_chain_to_idx[chain_idx] = img_count
                    img_count += 1

            # 对每张图片进行转文字
            image_descriptions = {}
            for idx, img_component in enumerate(image_components):
                try:
                    # 获取图片URL或路径
                    image_path = await img_component.convert_to_file_path()
                    if not image_path:
                        logger.warning(f"无法获取图片 {idx} 的路径")
                        continue

                    if DEBUG_MODE:
                        logger.info(f"正在转换图片 {idx}: {image_path}")

                    # 🆕 v1.2.0: 先检查本地缓存，命中则跳过AI调用
                    if image_description_cache and image_description_cache.enabled:
                        cached_desc = image_description_cache.lookup(image_path)
                        if cached_desc:
                            image_descriptions[idx] = cached_desc
                            logger.info(
                                f"[图片缓存] 图片 {idx} 命中缓存，跳过AI调用 (省钱!)"
                            )
                            continue

                    # 调用AI进行图片转文字,添加超时控制
                    async def call_vision_ai():
                        response = await provider.text_chat(
                            prompt=prompt,
                            contexts=[],
                            image_urls=[image_path],
                            func_tool=None,
                            system_prompt="",
                        )
                        return response.completion_text

                    # 使用用户配置的超时时间
                    description = await asyncio.wait_for(
                        call_vision_ai(), timeout=timeout
                    )

                    if description:
                        image_descriptions[idx] = description
                        if DEBUG_MODE:
                            logger.info(f"图片 {idx} 转换成功: {description[:50]}...")

                        # 🆕 v1.2.0: AI转换成功后，保存到本地缓存
                        # 🔧 防御性编程：保存前再次检查缓存中是否已存在
                        # 场景：并发处理两条含相同图片的消息，或平台描述已提前写入缓存
                        if image_description_cache and image_description_cache.enabled:
                            if not image_description_cache.lookup(image_path):
                                image_description_cache.save(image_path, description)

                except asyncio.TimeoutError:
                    logger.warning(
                        f"图片 {idx} 转文字超时（超过 {timeout} 秒），可在配置中调整 image_to_text_timeout 参数"
                    )
                    continue
                except Exception as e:
                    logger.error(f"转换图片 {idx} 时发生错误: {e}")
                    continue

            # 如果没有成功转换任何图片,返回None
            if not image_descriptions:
                logger.warning("没有成功转换任何图片")
                return None

            # 构建新的消息文本,将图片替换为描述
            result_parts = []
            for chain_idx, component in enumerate(message_chain):
                if isinstance(component, Plain):
                    result_parts.append(component.text)
                elif isinstance(component, Image):
                    # 如果这张图片有描述,使用描述替换
                    # 通过chain_idx找到对应的image_components索引
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
                    # 其他组件使用统一的格式化方法
                    formatted = ImageHandler._format_special_component(component)
                    if formatted:
                        result_parts.append(formatted)

            result_text = "".join(result_parts)
            if DEBUG_MODE:
                logger.info(f"图片转文字完成,处理后的消息: {result_text[:100]}...")
            return result_text

        except Exception as e:
            logger.error(f"图片转文字过程发生错误: {e}")
            return None
