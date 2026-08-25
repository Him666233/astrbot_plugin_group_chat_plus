import re
import logging

from astrbot.core.message.components import Plain, At

logger = logging.getLogger(__name__)

# <refuse/> 必须独占整条回复
REFUSE_PATTERN = re.compile(r"^\s*<refuse/>\s*$", re.IGNORECASE)

# <mention id="xxx"/> 或 <mention id='xxx'/>
MENTION_PATTERN = re.compile(
    r"""<mention\s+id\s*=\s*["']([^"']+)["']\s*/?>""",
    re.IGNORECASE,
)

# </mention> 关闭标签（清理用）
MENTION_CLOSE_PATTERN = re.compile(r"</mention\s*>", re.IGNORECASE)


def has_refuse_tag(text: str) -> bool:
    if not text:
        return False
    return bool(REFUSE_PATTERN.match(text))


def process_mention_tags(chain: list) -> list | None:
    has_mention = False
    for comp in chain:
        if hasattr(comp, "text") and (
            MENTION_PATTERN.search(comp.text)
            or MENTION_CLOSE_PATTERN.search(comp.text)
        ):
            has_mention = True
            break

    if not has_mention:
        return None

    new_chain = []
    for comp in chain:
        if not isinstance(comp, Plain):
            new_chain.append(comp)
            continue

        text = comp.text
        text = MENTION_CLOSE_PATTERN.sub("", text)

        if MENTION_PATTERN.search(text):
            parts = MENTION_PATTERN.split(text)
            for idx, part in enumerate(parts):
                if idx % 2 == 0:
                    cleaned = part.strip()
                    if cleaned:
                        new_chain.append(Plain(text=cleaned))
                else:
                    new_chain.append(At(qq=part))
        else:
            cleaned = text.strip()
            if cleaned:
                new_chain.append(Plain(text=cleaned))

    return new_chain


def build_tag_instructions(
    refuse_enabled: bool = True,
    mention_enabled: bool = True,
) -> str:
    parts = []
    parts.append("\n\n【控制标签说明】：")
    parts.append("你可以使用以下控制标签来影响消息的发送方式，这些标签是可选的，只在需要时使用：")

    if refuse_enabled:
        parts.append(
            '- `<refuse/>`：如果你认为当前不适合回复，'
            "请输出 `<refuse/>` 作为整条回复（必须独占整条回复，不能有其他文字），"
            "系统将不会发送这条消息。"
        )

    if mention_enabled:
        parts.append(
            '- `<mention id="用户ID"/>`：当你想在回复中 @ 某人时，'
            "使用此标签，系统会自动将其转换为 @ 消息。"
            '例如：`<mention id="123456"/> 你好呀！`'
        )

    parts.append(
        "注意：这些标签只在你觉得需要的时候使用，不是必须的。"
    )

    return "\n".join(parts)
