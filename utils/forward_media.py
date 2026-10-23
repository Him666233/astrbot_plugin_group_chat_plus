"""Bounded, message-scoped preparation of forwarded images.

Only callers referencing the same message share its task. Ordinary group
traffic is never held behind a group-wide lock. No task sends chat messages.
"""

import asyncio
import copy
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from astrbot.api import logger
from astrbot.core.message.components import Forward, Image, Plain, Reply

from .forward_message_parser import ForwardMessageParser, ForwardParseState


@dataclass(frozen=True)
class ForwardMediaPolicy:
    provider_id: str
    prompt: str
    max_images: int = 10
    timeout: float = 90
    include_sender: bool = True
    include_timestamp: bool = True
    max_depth: int = 3


@dataclass
class ForwardMediaResult:
    text: str
    status: str
    described: int = 0
    unread: int = 0
    chain: Optional[list] = None


@dataclass
class _Entry:
    task: asyncio.Task
    expires_at: float = float("inf")


def allows_image_caption(scope: str, is_at: bool, has_keyword: bool) -> bool:
    scope = (scope or "all").strip().lower()
    return {
        "all": True,
        "mention_only": is_at or has_keyword,
        "at_only": is_at,
        "keyword_only": has_keyword,
    }.get(scope, is_at or has_keyword)


class _ImageRenderer:
    def __init__(
        self, describe: Callable[[Image], Awaitable[Optional[str]]], limit: int
    ):
        self.describe = describe
        self.limit = max(0, limit)
        self.described = 0
        self.unread = 0
        self.results = {}

    async def __call__(self, data: dict) -> str:
        source = next(
            (
                data.get(key)
                for key in ("url", "file")
                if isinstance(data.get(key), str)
                and data[key].startswith(("https://", "http://"))
            ),
            None,
        )
        if not source:
            self.unread += 1
            return "[图片（没有可用的下载地址，尚未识别）]"
        if source in self.results:
            return self.results[source]
        if len(self.results) >= self.limit:
            self.unread += 1
            return "[图片（超过本条转发识图数量限制，尚未识别）]"
        self.results[source] = "[图片（识别失败，不能判断画面）]"
        try:
            description = await self.describe(Image.fromURL(source))
            if description:
                self.described += 1
                self.results[source] = f"[图片内容: {description}]"
            else:
                self.unread += 1
        except Exception as exc:
            self.unread += 1
            logger.warning(f"[Forward media] image_failed={type(exc).__name__}")
        return self.results[source]


class ForwardMediaProcessor:
    def __init__(self, max_entries: int = 100, ttl: float = 1800, clock=time.monotonic):
        self.max_entries = max_entries
        self.ttl = ttl
        self.clock = clock
        self._entries = OrderedDict()
        self._closed = False

    def _prune(self):
        now = self.clock()
        for key, entry in list(self._entries.items()):
            if entry.task.done() and entry.expires_at <= now:
                self._entries.pop(key, None)

    async def _resolve(
        self,
        key,
        factory,
        timeout,
        state: ForwardParseState,
    ):
        self._prune()
        entry = self._entries.get(key)
        if entry is None:
            if self._closed:
                text = "[转发处理已停止，内容尚未读取]"
                return ForwardMediaResult(text if state.is_forward else "", "closed")
            if len(self._entries) >= self.max_entries:
                for old_key, old_entry in list(self._entries.items()):
                    if old_entry.task.done():
                        self._entries.pop(old_key)
                        break
                else:
                    text = "[转发处理繁忙，内容尚未读取]"
                    return ForwardMediaResult(text if state.is_forward else "", "busy")

            async def run():
                try:
                    return await asyncio.wait_for(factory(), timeout=max(1, timeout))
                except asyncio.TimeoutError:
                    if not state.is_forward:
                        return ForwardMediaResult("", "unknown")
                    return ForwardMediaResult(
                        "[转发处理超时，内容未完整读取，请勿推测其中的图片]", "timeout"
                    )
                except Exception as exc:
                    logger.warning(
                        f"[Forward media] resolve_failed={type(exc).__name__}"
                    )
                    if not state.is_forward:
                        return ForwardMediaResult("", "unknown")
                    return ForwardMediaResult("[转发获取失败，内容尚未读取]", "failed")

            entry = _Entry(asyncio.create_task(run()))
            self._entries[key] = entry

            def finished(task):
                # Cancelled tasks have no usable result and must be retryable.
                if task.cancelled():
                    if self._entries.get(key) is entry:
                        self._entries.pop(key, None)
                    return
                result = task.result()
                lifetime = self.ttl if result.status in ("ready", "not_forward") else 5
                entry.expires_at = self.clock() + lifetime

            entry.task.add_done_callback(finished)
        self._entries.move_to_end(key)
        # A cancelled quoted request must not cancel the original message's work.
        return await asyncio.shield(entry.task)

    async def prepare(
        self,
        event,
        policy: ForwardMediaPolicy,
        describe,
    ) -> bool:
        """Prepare top-level forwards and exact quotes before text-only caching."""
        chain = event.message_obj.message
        if self._closed or not ForwardMessageParser.supports(event):
            return False
        session = event.unified_msg_origin
        options = dict(
            include_sender_info=policy.include_sender,
            include_timestamp=policy.include_timestamp,
            max_nesting_depth=policy.max_depth,
        )

        if any(isinstance(component, Forward) for component in chain):
            message_id = str(getattr(event.message_obj, "message_id", "") or "")
            # Missing platform IDs must never collide in the shared result cache.
            key = (session, message_id or object(), policy)
            snapshot = copy.copy(event)
            snapshot.message_obj = copy.copy(event.message_obj)
            snapshot.message_obj.message = list(chain)
            state = ForwardParseState(is_forward=True)

            async def load():
                renderer = _ImageRenderer(describe, policy.max_images)
                parsed = await ForwardMessageParser.try_parse_and_replace(
                    snapshot, **options, image_renderer=renderer, state=state
                )
                if not parsed:
                    return ForwardMediaResult("[转发未能展开，内容尚未读取]", "failed")
                return ForwardMediaResult(
                    snapshot.message_str,
                    "partial" if renderer.unread or state.incomplete else "ready",
                    renderer.described,
                    renderer.unread,
                    snapshot.message_obj.message,
                )

            result = await self._resolve(key, load, policy.timeout, state)
            if result.chain is not None:
                event.message_obj.message = list(result.chain)
            else:
                event.message_obj.message = [
                    Plain(text=result.text)
                    if isinstance(component, Forward)
                    else component
                    for component in chain
                ]
            self._sync_text(event)
            logger.info(
                f"[Forward media] status={result.status} "
                f"described={result.described} unread={result.unread}"
            )
            return True

        for index, reply in enumerate(chain):
            if not isinstance(reply, Reply):
                continue
            message_id = str(getattr(reply, "id", "") or "")
            if not message_id:
                continue
            key = (session, message_id, policy)
            state = ForwardParseState()

            async def load_quote(reply=reply, state=state):
                renderer = _ImageRenderer(describe, policy.max_images)
                text = await ForwardMessageParser.parse_quoted_forward(
                    event, reply, **options, image_renderer=renderer, state=state
                )
                if text is None:
                    return ForwardMediaResult("", "not_forward")
                return ForwardMediaResult(
                    text,
                    "partial" if renderer.unread or state.incomplete else "ready",
                    renderer.described,
                    renderer.unread,
                )

            result = await self._resolve(key, load_quote, policy.timeout, state)
            if result.text:
                # Replace the component without mutating another event's quote.
                reply = copy.copy(reply)
                reply.message_str = result.text
                reply.chain = [Plain(text=result.text)]
                chain = list(chain)
                chain[index] = reply
                event.message_obj.message = chain
                logger.info(f"[Forward media] quote_status={result.status}")
        return False

    @staticmethod
    def _sync_text(event):
        text = " ".join(
            component.text
            if isinstance(component, Plain)
            else f"[{getattr(component, 'type', 'Unknown')}]"
            for component in event.message_obj.message
        )
        event.message_obj.message_str = text
        event.message_str = text

    async def close(self):
        self._closed = True
        tasks = [entry.task for entry in self._entries.values()]
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._entries.clear()
