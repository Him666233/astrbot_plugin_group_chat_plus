"""块锚定（缓存友好）上下文窗口的单元测试。

只测纯逻辑，不依赖 AstrBot 运行时 —— 模块通过文件路径直接加载，
绕开 ``utils/__init__.py``（那个会 import 整个插件栈）。
"""

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "utils" / "context_window.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "context_window_under_test", _MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cw = _load_module()


class FakeSender:
    def __init__(self, user_id="u1"):
        self.user_id = user_id


class FakeMessage:
    """最小消息替身：只需要锚点用到的几个字段。"""

    def __init__(self, idx, message_id=None, sender_id="u1"):
        self.message_id = message_id if message_id is not None else f"m{idx}"
        self.message_str = f"message-{idx}"
        self.timestamp = 1_700_000_000 + idx
        self.sender = FakeSender(sender_id)

    def __repr__(self):
        return f"FakeMessage({self.message_id})"


# --------------------------------------------------------------- 关闭时无副作用


def test_disabled_returns_input_unchanged():
    """block<=0 必须完全等于旧行为：原样返回，不写锚点。"""
    msgs = [FakeMessage(i) for i in range(200)]
    anchors = {}

    result = cw.anchored_window("g1", msgs, 80, 0, anchors)

    assert result.window is msgs
    assert result.advanced == 0
    assert anchors == {}


def test_below_limit_returns_input_unchanged():
    msgs = [FakeMessage(i) for i in range(50)]
    anchors = {}

    result = cw.anchored_window("g1", msgs, 80, 20, anchors)

    assert result.window is msgs
    assert anchors == {}


# ------------------------------------------------------------------- 基本行为


def test_first_call_takes_tail_and_records_anchor():
    msgs = [FakeMessage(i) for i in range(100)]
    anchors = {}

    result = cw.anchored_window("g1", msgs, 80, 20, anchors)

    assert len(result.window) == 80
    assert result.window[0] is msgs[20]
    assert anchors["g1"] == cw.message_key(msgs[20])


def test_head_stays_put_while_under_limit():
    """窗口没顶到上限时，头部必须一动不动 —— 这是缓存命中的前提。"""
    msgs = [FakeMessage(i) for i in range(100)]
    anchors = {}
    cw.anchored_window("g1", msgs, 80, 20, anchors)  # start=20, len=80

    msgs.append(FakeMessage(100))
    result = cw.anchored_window("g1", msgs, 80, 20, anchors)  # 溢出一次 -> start=40
    assert result.advanced == 1
    head = result.window[0]

    for extra in range(10):
        msgs.append(FakeMessage(101 + extra))
        again = cw.anchored_window("g1", msgs, 80, 20, anchors)
        assert again.window[0] is head
        assert again.advanced == 0


def test_advance_moves_in_whole_blocks():
    msgs = [FakeMessage(i) for i in range(100)]
    anchors = {}
    cw.anchored_window("g1", msgs, 80, 20, anchors)  # start=20

    msgs.extend(FakeMessage(100 + i) for i in range(21))  # 溢出 21 条 -> 需要 2 块
    result = cw.anchored_window("g1", msgs, 80, 20, anchors)

    assert result.advanced == 2
    assert result.start == 60
    assert result.anchor_found is True


def test_window_length_within_bounds():
    """窗口长度必须落在 (limit-block, limit]。"""
    limit, block = 80, 20
    msgs = [FakeMessage(i) for i in range(100)]
    anchors = {}

    for turn in range(60):
        msgs.append(FakeMessage(100 + turn))
        result = cw.anchored_window("g1", msgs, limit, block, anchors)
        assert limit - block < len(result.window) <= limit


def test_heads_stay_stable_across_many_turns():
    """40 轮里头部只应在跨块时变化，次数远少于轮数。"""
    msgs = [FakeMessage(i) for i in range(100)]
    anchors = {}
    heads = []

    for turn in range(40):
        msgs.append(FakeMessage(100 + turn))
        heads.append(cw.anchored_window("g1", msgs, 80, 20, anchors).window[0])

    assert len(set(heads)) <= 4
    assert len(heads) == 40


def test_oversized_block_is_clamped():
    """block 逼近上限时会把窗口挤成个位数，必须夹到上限的一半。"""
    msgs = [FakeMessage(i) for i in range(80)]
    anchors = {}

    for block in (41, 60, 79, 80, 200):
        anchors.clear()
        lens = []
        for turn in range(1, 30):
            msgs.append(FakeMessage(80 + turn))
            result = cw.anchored_window("g1", msgs, 80, block, anchors)
            lens.append(len(result.window))
        assert min(lens) >= 40, (block, min(lens))


def test_block_at_half_limit_is_allowed():
    """恰好一半是合法边界，不该被夹。"""
    msgs = [FakeMessage(i) for i in range(80)]
    anchors = {}
    cw.anchored_window("g1", msgs, 80, 40, anchors)  # 未超限：原样返回，不落锚

    msgs.append(FakeMessage(80))
    first = cw.anchored_window("g1", msgs, 80, 40, anchors)  # 首次超限：取末尾并落锚
    assert first.advanced == 0
    assert len(first.window) == 80

    msgs.append(FakeMessage(81))  # 82 条 → 真正溢出 → 前移 40
    result = cw.anchored_window("g1", msgs, 80, 40, anchors)

    assert result.advanced == 1
    assert len(result.window) == 41


def test_anchor_lost_falls_back_to_tail():
    """锚点掉出列表（被过滤/清空）时退回末尾窗口，并重建锚点。"""
    msgs = [FakeMessage(i) for i in range(100)]
    anchors = {}
    cw.anchored_window("g1", msgs, 80, 20, anchors)

    fresh = [FakeMessage(1000 + i) for i in range(120)]
    result = cw.anchored_window("g1", fresh, 80, 20, anchors)

    assert result.anchor_found is False
    assert len(result.window) == 80
    assert result.window[0] is fresh[40]
    assert anchors["g1"] == cw.message_key(fresh[40])


def test_chats_do_not_share_anchors():
    a = [FakeMessage(i) for i in range(100)]
    b = [FakeMessage(i) for i in range(100)]
    anchors = {}

    cw.anchored_window("gA", a, 80, 20, anchors)
    cw.anchored_window("gB", b, 80, 20, anchors)

    assert anchors["gA"] == cw.message_key(a[20])
    assert anchors["gB"] == cw.message_key(b[20])


# ------------------------------------------------------------------- 锚点键


def test_message_key_prefers_message_id():
    msg = FakeMessage(1, message_id="real-id")
    assert cw.message_key(msg) == ("id", "real-id")


def test_message_key_falls_back_for_cached_ids():
    """缓存消息的 id 形如 cached_<ts>，会被重新组装，不能当锚点。"""
    msg = FakeMessage(1, message_id="cached_1700000001")
    key = cw.message_key(msg)

    assert key[0] == "c"
    assert key[1] == "message-1"


def test_message_key_survives_rebuild():
    """同一条消息被重新组装成新对象，键必须一致。"""
    a = FakeMessage(7)
    b = FakeMessage(7)
    assert a is not b
    assert cw.message_key(a) == cw.message_key(b)
