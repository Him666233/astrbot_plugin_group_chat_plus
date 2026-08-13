"""
多媒体消息处理模块
负责处理消息中的各类媒体内容：
- 图片：检测、过滤、转文字（AI 描述）或多模态直传
- 视频：文件路径提取，内联标记注入
- 语音/音频：文件路径提取，内联标记注入
- 文件：文件路径与名称提取，内联标记注入

同时负责缓存剥离前的标记富化（将文件路径注入占位标记中）

作者: Him666233
版本: V1.2.3.hotfix.2
"""

import asyncio
from typing import List, Optional, Tuple, Any
from astrbot.api.all import *
from astrbot.api.message_components import Face, At, AtAll, Reply

# 尝试导入非文本媒体组件（不同 AstrBot 版本路径可能不同）
try:
    from astrbot.core.message.components import Video, Record, File
except ImportError:
    try:
        from astrbot.api.message_components import Video, Record, File
    except ImportError:
        Video = None
        Record = None
        File = None

from .image_description_cache import ImageDescriptionCache
from .ai_error_formatter import format_ai_error

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False

# AstrBot 的 Reply 组件会在 chain 字段中保存被引用消息的原始消息段。
# 限制递归深度，避免异常平台数据构造循环/超深引用链。
_MAX_REPLY_NESTING_DEPTH: int = 3


class ImageHandler:
    """
    多媒体消息处理器

    主要功能：
    1. 检测消息中的图片，过滤纯图片或移除图片
    2. 调用AI将图片转为文字描述，或将图片URL直传给多模态AI
    3. 提取视频、语音(Record)、文件(File)组件的文件路径
    4. 将媒体文件路径内联注入到消息文本的占位标记中（如 [视频: /path]）
    5. 将图片描述融入原消息
    """

    @staticmethod
    def _coerce_plain_text(value: Any) -> str:
        """兼容某些平台 Plain.text=None 的情况。"""
        return value if isinstance(value, str) else ""

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
        self_id: str = None,
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
            self_id: 机器人自身的用户ID，用于标记引用消息发送者是否为AI自己

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
                text_content = ImageHandler._extract_text_only(
                    message_chain, self_id=self_id
                )
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
                    text_only = ImageHandler._extract_text_only(
                        message_chain, self_id=self_id
                    )
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
                    text_only = ImageHandler._extract_text_only(
                        message_chain, self_id=self_id
                    )
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
                # 提取文本内容 — 保留 [图片] 标记作为占位符，与视频/语音/文件标记行为一致。
                # Reply.chain 中的引用图片也会递归展开；图片URL列表与这些标记顺序一致。
                text_content = ImageHandler._render_message_chain(
                    message_chain,
                    self_id=self_id,
                    include_images=True,
                )
                if DEBUG_MODE:
                    logger.info(
                        f"🟢 [多模态模式] 提取到 {len(image_urls)} 张图片，文本内容: {text_content[:100] if text_content else '(无文本)'}"
                    )
                return (
                    True,
                    text_content,
                    image_urls,
                    True,
                )  # 多模态: 图片保留为URL，文本保留[图片]标记

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
                getattr(event, "session_id", ""),
                self_id=self_id,
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
                            fmt = ImageHandler._format_special_component(
                                comp, self_id=self_id
                            )
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
                    text_only = ImageHandler._extract_text_only(
                        message_chain, self_id=self_id
                    )
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

        def walk_chain(chain: List[BaseMessageComponent], depth: int = 0) -> None:
            nonlocal has_image, has_text

            for component in chain:
                if isinstance(component, Image):
                    has_image = True
                    image_components.append(component)
                elif isinstance(component, Plain):
                    # 检查是否有非空白文字
                    if ImageHandler._coerce_plain_text(component.text).strip():
                        has_text = True
                elif isinstance(component, Reply):
                    # 引用本身也视为文字内容，防止「引用+图片」被当作纯图片丢弃。
                    has_text = True
                    if depth < _MAX_REPLY_NESTING_DEPTH:
                        reply_chain = ImageHandler._get_reply_chain(component)
                        if reply_chain:
                            walk_chain(reply_chain, depth + 1)
                elif Video is not None and isinstance(component, Video):
                    # 视频消息视为有内容，防止纯视频消息被丢弃
                    has_text = True
                elif Record is not None and isinstance(component, Record):
                    # 语音消息视为有内容，防止纯语音消息被丢弃
                    has_text = True
                elif File is not None and isinstance(component, File):
                    # 文件消息视为有内容，防止纯文件消息被丢弃
                    has_text = True

        walk_chain(message_chain)

        # 限制单条消息处理的图片数量，防止恶意刷图
        if len(image_components) > max_images:
            logger.warning(
                f"[图片处理] 单条消息包含 {len(image_components)} 张图片，"
                f"超过上限 {max_images}，仅处理前 {max_images} 张"
            )
            image_components = image_components[:max_images]

        return has_image, has_text, image_components

    @staticmethod
    def _get_reply_chain(component: Reply) -> List[BaseMessageComponent]:
        """安全获取 Reply 组件内嵌的原始消息链。"""
        chain = getattr(component, "chain", None)
        if isinstance(chain, (list, tuple)):
            return list(chain)
        return []

    @staticmethod
    def _format_reply_component(
        component: Reply,
        message_content: Optional[str] = None,
        self_id: str = None,
    ) -> str:
        """将引用组件格式化为包含发送者与引用正文的文本块。"""
        try:
            sender_nickname = getattr(
                component, "sender_nickname", None
            ) or getattr(component, "sender_name", None)
            if not sender_nickname and hasattr(component, "sender"):
                sender_nickname = getattr(component.sender, "nickname", None)
            sender_id = getattr(component, "sender_id", None)

            if message_content is None:
                # 优先使用结构化 chain，以便保留被引用消息中的图片占位符。
                reply_chain = ImageHandler._get_reply_chain(component)
                if reply_chain:
                    message_content = ImageHandler._render_message_chain(
                        reply_chain,
                        self_id=self_id,
                        include_images=True,
                        _depth=1,
                    ).strip()

                if not message_content:
                    message_content = getattr(
                        component, "message_str", None
                    ) or getattr(component, "message", None)

            if message_content is not None and not isinstance(message_content, str):
                message_content = str(message_content)
            message_content = (message_content or "").strip()

            if (
                sender_nickname
                and sender_id
                and str(sender_nickname) == str(sender_id)
            ):
                sender_nickname = None
            is_self = self_id and sender_id and str(sender_id) == str(self_id)
            self_suffix = "(你)" if is_self else ""

            if message_content:
                if sender_nickname and sender_id:
                    reply_text = f"[引用 >>> {sender_nickname}{self_suffix}(ID:{sender_id}): {message_content}]"
                elif sender_id:
                    reply_text = f"[引用 >>> 未知用户{self_suffix}(ID:{sender_id}): {message_content}]"
                elif sender_nickname:
                    reply_text = (
                        f"[引用 >>> {sender_nickname}{self_suffix}: {message_content}]"
                    )
                else:
                    reply_text = f"[引用 >>> {message_content}]"
            elif sender_nickname and sender_id:
                reply_text = f"[引用 >>> {sender_nickname}{self_suffix}(ID:{sender_id}): (无法获取引用内容)]"
            elif sender_id:
                reply_text = f"[引用 >>> 未知用户{self_suffix}(ID:{sender_id}): (无法获取引用内容)]"
            elif sender_nickname:
                reply_text = (
                    f"[引用 >>> {sender_nickname}{self_suffix}: (无法获取引用内容)]"
                )
            else:
                return ""

            return reply_text.rstrip() + "\n"
        except Exception:
            return ""

    @staticmethod
    def _render_message_chain(
        message_chain: List[BaseMessageComponent],
        self_id: str = None,
        include_images: bool = True,
        image_descriptions: Optional[dict] = None,
        _image_index: Optional[List[int]] = None,
        _depth: int = 0,
    ) -> str:
        """
        将消息链渲染为文本，并递归处理 Reply.chain。

        image_descriptions 使用图片在展开后消息链中的顺序索引作为键，确保
        引用图片与普通图片共用同一套图片数量限制和视觉识别结果映射。
        """
        if _image_index is None:
            _image_index = [0]

        result_parts = []
        for component in message_chain:
            if isinstance(component, Plain):
                result_parts.append(ImageHandler._coerce_plain_text(component.text))
            elif isinstance(component, Image):
                image_idx = _image_index[0]
                _image_index[0] += 1
                if include_images:
                    description = (image_descriptions or {}).get(image_idx)
                    if description:
                        result_parts.append(f"[图片内容: {description}]")
                    else:
                        result_parts.append("[图片]")
            elif isinstance(component, Reply):
                nested_content = ""
                if _depth < _MAX_REPLY_NESTING_DEPTH:
                    reply_chain = ImageHandler._get_reply_chain(component)
                    if reply_chain:
                        nested_content = ImageHandler._render_message_chain(
                            reply_chain,
                            self_id=self_id,
                            include_images=include_images,
                            image_descriptions=image_descriptions,
                            _image_index=_image_index,
                            _depth=_depth + 1,
                        ).strip()

                if not nested_content:
                    nested_content = getattr(
                        component, "message_str", None
                    ) or getattr(component, "message", None)

                formatted = ImageHandler._format_reply_component(
                    component,
                    message_content=nested_content or "",
                    self_id=self_id,
                )
                if formatted:
                    result_parts.append(formatted)
            else:
                formatted = ImageHandler._format_special_component(
                    component, self_id=self_id
                )
                if formatted:
                    result_parts.append(formatted)

        return "".join(result_parts)

    @staticmethod
    def _format_special_component(
        component: BaseMessageComponent, self_id: str = None
    ) -> str:
        """
        格式化特殊消息组件为文本表示

        Args:
            component: 消息组件
            self_id: 机器人自身的用户ID，用于标记引用消息发送者是否为AI自己

        Returns:
            格式化后的文本，如果不是特殊组件返回空字符串
        """
        if isinstance(component, Face):
            return f"[表情:{component.id}]"
        elif isinstance(component, At):
            return f"[At:{component.qq}]"
        elif isinstance(component, AtAll):
            return "[At:all]"
        elif isinstance(component, Reply):
            return ImageHandler._format_reply_component(
                component,
                self_id=self_id,
            )
        elif Video is not None and isinstance(component, Video):
            return "[视频]"
        elif Record is not None and isinstance(component, Record):
            return "[语音]"
        elif File is not None and isinstance(component, File):
            file_name = getattr(component, "name", "") or ""
            if file_name:
                return f"[文件: {file_name}]"
            return "[文件]"
        else:
            return ""

    @staticmethod
    def _extract_text_only(
        message_chain: List[BaseMessageComponent], self_id: str = None
    ) -> str:
        """
        从消息链提取纯文字，过滤图片

        Args:
            message_chain: 消息链
            self_id: 机器人自身的用户ID，用于标记引用消息发送者是否为AI自己

        Returns:
            纯文字内容
        """
        result = ImageHandler._render_message_chain(
            message_chain,
            self_id=self_id,
            include_images=False,
        ).strip()
        if not result:
            logger.warning(
                "[图片处理] _extract_text_only 提取到空文本！"
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
    async def extract_media_urls(
        event: AstrMessageEvent,
    ) -> Tuple[List[str], List[str], List[dict]]:
        """
        从消息事件中提取非图片媒体文件的路径/URL（结构化返回）

        Args:
            event: 消息事件

        Returns:
            (audio_urls, video_paths, file_infos)
            - audio_urls: 语音文件路径列表（传给 ProviderRequest.audio_urls）
            - video_paths: 视频文件路径列表（按消息链顺序）
            - file_infos: 文件信息列表 [{"name": str, "path": str}, ...]（按消息链顺序）
        """
        audio_urls: List[str] = []
        video_paths: List[str] = []
        file_infos: List[dict] = []

        try:
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return audio_urls, video_paths, file_infos

            message_chain = event.message_obj.message
            for component in message_chain:
                # 语音/音频组件 → audio_urls
                if Record is not None and isinstance(component, Record):
                    try:
                        audio_path = await component.convert_to_file_path()
                        if audio_path:
                            audio_urls.append(audio_path)
                            if DEBUG_MODE:
                                logger.info(f"[媒体提取] 语音文件: {audio_path}")
                    except Exception as e:
                        logger.warning(f"[媒体提取] 提取语音文件路径失败: {e}")

                # 视频组件 → video_paths
                elif Video is not None and isinstance(component, Video):
                    try:
                        video_path = await component.convert_to_file_path()
                        if video_path:
                            video_paths.append(video_path)
                            if DEBUG_MODE:
                                logger.info(f"[媒体提取] 视频文件: {video_path}")
                    except Exception as e:
                        logger.warning(f"[媒体提取] 提取视频文件路径失败: {e}")

                # 文件组件 → file_infos
                elif File is not None and isinstance(component, File):
                    try:
                        file_path = await component.get_file()
                        file_name = getattr(component, "name", "") or ""
                        if not file_name and file_path:
                            import os

                            file_name = os.path.basename(file_path)
                        file_infos.append(
                            {
                                "name": file_name,
                                "path": file_path or "",
                            }
                        )
                        if DEBUG_MODE:
                            logger.info(f"[媒体提取] 文件: {file_name} -> {file_path}")
                    except Exception as e:
                        logger.warning(f"[媒体提取] 提取文件信息失败: {e}")

        except Exception as e:
            logger.warning(f"[媒体提取] 提取媒体URL时出错: {e}")

        return audio_urls, video_paths, file_infos

    @staticmethod
    def enrich_media_markers(
        message_text: str,
        audio_urls: List[str],
        video_paths: List[str],
        file_infos: List[dict],
    ) -> str:
        """
        将媒体文件路径内联注入到消息文本的占位标记中

        解析成功时:  [语音] → [语音: /path/to/audio.amr]
                     [视频] → [视频: /path/to/video.mp4]
                     [文件: name] → [文件: name, /path/to/file]
                     [文件] → [文件: /path/to/file]
        解析失败时:  占位标记保持原样（无路径追加），充当降级占位符

        Args:
            message_text: 含占位标记的消息文本
            audio_urls: 语音文件路径列表（与文本中 [语音] 出现顺序对应）
            video_paths: 视频文件路径列表（与文本中 [视频] 出现顺序对应）
            file_infos: 文件信息列表（与文本中 [文件: ...] 出现顺序对应）

        Returns:
            内联了文件路径的富文本
        """
        result = message_text

        # 按顺序逐一替换 [语音] → [语音: path]
        for audio_path in audio_urls:
            result = result.replace("[语音]", f"[语音: {audio_path}]", 1)

        # 按顺序逐一替换 [视频] → [视频: path]
        for video_path in video_paths:
            result = result.replace("[视频]", f"[视频: {video_path}]", 1)

        # 按顺序逐一替换 [文件: name] → [文件: name, path] 或 [文件] → [文件: path]
        for fi in file_infos:
            name = fi.get("name", "")
            path = fi.get("path", "")
            if name:
                old = f"[文件: {name}]"
                new = f"[文件: {name}, {path}]" if path else old
            else:
                old = "[文件]"
                new = f"[文件: {path}]" if path else old
            result = result.replace(old, new, 1)

        return result

    @staticmethod
    async def _convert_images_to_text(
        message_chain: List[BaseMessageComponent],
        context: Context,
        provider_id: str,
        prompt: str,
        image_components: List[Image],
        timeout: int = 60,
        image_description_cache: Optional[ImageDescriptionCache] = None,
        session_id: str = "",
        self_id: str = None,
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
            session_id: 会话ID
            self_id: 机器人自身的用户ID，用于标记引用消息发送者是否为AI自己

        Returns:
            转换后的文本，失败返回None
        """
        try:
            # 获取指定的提供商
            provider = context.get_provider_by_id(provider_id)
            if not provider:
                logger.error(f"无法找到提供商: {provider_id}")
                return None

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
                            session_id=session_id,
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
                    logger.error(f"{format_ai_error(e, f'图片转文字-{idx}')}")
                    continue

            # 如果没有成功转换任何图片,返回None
            if not image_descriptions:
                logger.warning("没有成功转换任何图片")
                return None

            # 构建新的消息文本，将普通图片和 Reply.chain 中的引用图片替换为描述。
            result_text = ImageHandler._render_message_chain(
                message_chain,
                self_id=self_id,
                include_images=True,
                image_descriptions=image_descriptions,
            )
            if DEBUG_MODE:
                logger.info(f"图片转文字完成,处理后的消息: {result_text[:100]}...")
            return result_text

        except Exception as e:
            logger.error(f"图片转文字过程发生错误: {e}")
            return None
