"""
时间段概率管理器 - Time Period Manager

负责根据时间段动态调整概率系数，模拟人类作息规律

核心功能：
1. 解析和验证时间段配置
2. 计算当前时间的概率系数
3. 平滑过渡（支持线性和自然曲线）
4. 安全限制（最低/最高系数）
5. 跨天时间段支持

作者: Him666233
版本: v1.1.0
"""

import json
import math
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from astrbot import logger

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class TimePeriodManager:
    """
    时间段概率管理器

    用于根据配置的时间段动态调整概率系数
    支持多个时间段、平滑过渡、自然曲线等功能
    """

    # 缓存已解析的配置，避免重复解析和重复输出日志
    _parsed_cache: Dict[str, List[Dict]] = {}

    # ========== 缓动函数 ==========

    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        """
        三次贝塞尔曲线（ease-in-out）

        模拟人类注意力的自然变化：
        - 开始慢：刚醒来/刚进入状态，注意力缓慢上升
        - 中间快：完全进入状态，变化较快
        - 结束慢：逐渐困倦/退出状态，变化又变缓慢

        这种非匀速变化更符合人类的生理规律

        Args:
            t: 进度值 (0.0-1.0)

        Returns:
            调整后的进度值 (0.0-1.0)
        """
        if t < 0.5:
            # 前半段：加速
            return 4 * t * t * t
        else:
            # 后半段：减速
            return 1 - pow(-2 * t + 2, 3) / 2

    @staticmethod
    def ease_in_out_sine(t: float) -> float:
        """
        正弦曲线（ease-in-out）

        相比三次曲线更加柔和，适合模拟缓慢的情绪/状态变化

        Args:
            t: 进度值 (0.0-1.0)

        Returns:
            调整后的进度值 (0.0-1.0)
        """
        return -(math.cos(math.pi * t) - 1) / 2

    # ========== 时间解析 ==========

    @staticmethod
    def parse_time_periods(periods_json: str, silent: bool = False) -> List[Dict]:
        """
        解析时间段配置JSON

        Args:
            periods_json: JSON格式的时间段配置字符串
            silent: 是否静默模式（不输出日志），用于重复调用时避免重复日志

        Returns:
            验证通过的时间段列表

        示例配置：
        [
            {
                "name": "深夜睡眠",
                "start": "23:00",
                "end": "07:00",
                "factor": 0.2
            },
            {
                "name": "晚间活跃",
                "start": "19:00",
                "end": "22:00",
                "factor": 1.5
            }
        ]
        """
        # 检查缓存
        if periods_json in TimePeriodManager._parsed_cache:
            return TimePeriodManager._parsed_cache[periods_json]

        try:
            # 空配置检查
            if not periods_json or periods_json.strip() == "":
                if not silent and DEBUG_MODE:
                    logger.info("[时间段配置] 配置为空，使用默认值")
                result = []
                TimePeriodManager._parsed_cache[periods_json] = result
                return result

            # JSON解析
            periods = json.loads(periods_json)

            # 格式验证
            if not isinstance(periods, list):
                if not silent:
                    logger.error("[时间段配置] 配置必须是列表格式")
                result = []
                TimePeriodManager._parsed_cache[periods_json] = result
                return result

            # 逐个验证时间段
            validated_periods = []
            for idx, period in enumerate(periods):
                if not isinstance(period, dict):
                    logger.warning(
                        f"[时间段配置] 第{idx + 1}个时间段不是字典格式，跳过: {period}"
                    )
                    continue

                # 检查必需字段
                if "start" not in period:
                    logger.warning(
                        f"[时间段配置] 第{idx + 1}个时间段缺少'start'字段，跳过"
                    )
                    continue
                if "end" not in period:
                    logger.warning(
                        f"[时间段配置] 第{idx + 1}个时间段缺少'end'字段，跳过"
                    )
                    continue
                if "factor" not in period:
                    logger.warning(
                        f"[时间段配置] 第{idx + 1}个时间段缺少'factor'字段，跳过"
                    )
                    continue

                # 验证时间格式
                try:
                    start_hour, start_minute = TimePeriodManager._parse_time_str(
                        period["start"]
                    )
                    end_hour, end_minute = TimePeriodManager._parse_time_str(
                        period["end"]
                    )
                except Exception as e:
                    logger.warning(
                        f"[时间段配置] 第{idx + 1}个时间段时间格式错误，跳过: {e}"
                    )
                    continue

                # 验证factor值
                try:
                    factor = float(period["factor"])
                    if factor < 0:
                        logger.warning(
                            f"[时间段配置] 第{idx + 1}个时间段factor不能为负数: {factor}，跳过"
                        )
                        continue
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"[时间段配置] 第{idx + 1}个时间段factor格式错误，跳过: {e}"
                    )
                    continue

                # 验证通过，添加到列表
                validated_periods.append(period)

                # 输出详细信息（仅debug模式，且非静默模式）
                if not silent and DEBUG_MODE:
                    name = period.get("name", f"时间段{idx + 1}")
                    logger.info(
                        f"[时间段配置] 已加载: {name} "
                        f"({period['start']}-{period['end']}, factor={factor:.2f})"
                    )

            # 只在非静默模式下输出成功加载日志
            if validated_periods and not silent and DEBUG_MODE:
                logger.info(f"[时间段配置] 成功加载 {len(validated_periods)} 个时间段")

            # 缓存结果
            TimePeriodManager._parsed_cache[periods_json] = validated_periods
            return validated_periods

        except json.JSONDecodeError as e:
            if not silent:
                logger.error(f"[时间段配置] JSON解析失败: {e}")
            result = []
            TimePeriodManager._parsed_cache[periods_json] = result
            return result
        except Exception as e:
            if not silent:
                logger.error(f"[时间段配置] 解析时发生未知错误: {e}", exc_info=True)
            result = []
            TimePeriodManager._parsed_cache[periods_json] = result
            return result

    @staticmethod
    def _parse_time_str(time_str: str) -> Tuple[int, int]:
        """
        解析时间字符串 "HH:MM" -> (hour, minute)

        Args:
            time_str: 时间字符串，格式为 "HH:MM"

        Returns:
            (小时, 分钟) 元组

        Raises:
            ValueError: 时间格式错误或超出范围
        """
        if not isinstance(time_str, str):
            raise ValueError(f"时间必须是字符串格式: {type(time_str)}")

        parts = time_str.strip().split(":")
        if len(parts) < 1 or len(parts) > 2:
            raise ValueError(f"时间格式错误，应为'HH:MM': {time_str}")

        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            raise ValueError(f"时间包含非数字字符: {time_str}")

        # 范围验证
        if not (0 <= hour <= 23):
            raise ValueError(f"小时必须在0-23之间: {hour}")
        if not (0 <= minute <= 59):
            raise ValueError(f"分钟必须在0-59之间: {minute}")

        return (hour, minute)

    @staticmethod
    def _time_to_minutes(hour: int, minute: int) -> int:
        """
        将时间转换为一天中的分钟数 (0-1439)

        Args:
            hour: 小时 (0-23)
            minute: 分钟 (0-59)

        Returns:
            一天中的分钟数
        """
        return hour * 60 + minute

    # ========== 时间段判断 ==========

    @staticmethod
    def _is_in_period(
        current_minutes: int, start_minutes: int, end_minutes: int
    ) -> bool:
        """
        判断当前时间是否在指定时间段内

        支持跨天时间段（如 23:00-07:00）

        Args:
            current_minutes: 当前时间（分钟数）
            start_minutes: 开始时间（分钟数）
            end_minutes: 结束时间（分钟数）

        Returns:
            是否在时间段内
        """
        if start_minutes > end_minutes:
            # 跨天情况：23:00-07:00
            # 在时间段内 = (当前>=开始) 或 (当前<结束)
            return current_minutes >= start_minutes or current_minutes < end_minutes
        else:
            # 不跨天情况：09:00-18:00
            # 在时间段内 = (开始<=当前<结束)
            return start_minutes <= current_minutes < end_minutes

    @staticmethod
    def _is_in_transition_range(
        current_minutes: int,
        boundary_minutes: int,
        transition_minutes: int,
        is_entering: bool,
    ) -> Tuple[bool, float]:
        """
        判断当前时间是否在过渡期内，并计算过渡进度

        Args:
            current_minutes: 当前时间（分钟数）
            boundary_minutes: 边界时间（开始或结束）
            transition_minutes: 过渡时长
            is_entering: True=进入过渡期, False=离开过渡期

        Returns:
            (是否在过渡期, 过渡进度0.0-1.0)
        """
        if is_entering:
            # 进入过渡期：边界前transition_minutes到边界
            transition_start = boundary_minutes - transition_minutes
            if transition_start < 0:
                transition_start += 1440  # 跨天处理

            # 判断是否在过渡期
            if transition_start < boundary_minutes:
                # 不跨天
                is_in_range = transition_start <= current_minutes < boundary_minutes
                if is_in_range:
                    progress = (current_minutes - transition_start) / transition_minutes
                    return True, progress
            else:
                # 跨天
                is_in_range = (
                    current_minutes >= transition_start
                    or current_minutes < boundary_minutes
                )
                if is_in_range:
                    if current_minutes >= transition_start:
                        distance = current_minutes - transition_start
                    else:
                        distance = 1440 - transition_start + current_minutes
                    progress = distance / transition_minutes
                    return True, progress
        else:
            # 离开过渡期：边界到边界后transition_minutes
            transition_end = boundary_minutes + transition_minutes
            if transition_end >= 1440:
                transition_end -= 1440  # 跨天处理

            # 判断是否在过渡期
            if boundary_minutes < transition_end:
                # 不跨天
                is_in_range = boundary_minutes <= current_minutes < transition_end
                if is_in_range:
                    progress = (current_minutes - boundary_minutes) / transition_minutes
                    return True, progress
            else:
                # 跨天
                is_in_range = (
                    current_minutes >= boundary_minutes
                    or current_minutes < transition_end
                )
                if is_in_range:
                    if current_minutes >= boundary_minutes:
                        distance = current_minutes - boundary_minutes
                    else:
                        distance = 1440 - boundary_minutes + current_minutes
                    progress = distance / transition_minutes
                    return True, progress

        return False, 0.0

    # ========== 主要计算方法 ==========

    @staticmethod
    def calculate_time_factor(
        current_time: Optional[datetime] = None,
        periods_config: Optional[List[Dict]] = None,
        transition_minutes: int = 30,
        min_factor: float = 0.1,
        max_factor: float = 2.0,
        use_smooth_curve: bool = True,
    ) -> float:
        """
        计算当前时间的概率系数

        这是核心方法，根据当前时间和配置计算出一个系数，
        用于调整AI的回复概率，模拟人类的作息规律

        Args:
            current_time: 当前时间（None则使用系统时间）
            periods_config: 时间段配置列表
            transition_minutes: 过渡时长（分钟）
            min_factor: 最低系数限制
            max_factor: 最高系数限制
            use_smooth_curve: 是否使用平滑曲线（推荐True）

        Returns:
            概率系数 (min_factor 到 max_factor 之间)

        工作流程：
        1. 遍历所有时间段
        2. 检查是否在某个时间段内 -> 直接返回该factor
        3. 检查是否在过渡期 -> 计算渐变factor
        4. 都不在 -> 返回1.0（正常状态）
        5. 应用最低/最高限制
        """
        # 使用当前时间
        if current_time is None:
            current_time = datetime.now()

        # 无配置，返回默认值
        if not periods_config:
            return 1.0

        # 转换为分钟数
        current_minutes = TimePeriodManager._time_to_minutes(
            current_time.hour, current_time.minute
        )

        # 记录匹配结果
        matched_factor = None  # 完全匹配的时间段
        transition_info = None  # 过渡期信息 (from_factor, to_factor, progress)

        # 遍历所有时间段
        for period in periods_config:
            try:
                # 解析时间段
                start_hour, start_minute = TimePeriodManager._parse_time_str(
                    period["start"]
                )
                end_hour, end_minute = TimePeriodManager._parse_time_str(period["end"])
                target_factor = float(period["factor"])

                start_minutes = TimePeriodManager._time_to_minutes(
                    start_hour, start_minute
                )
                end_minutes = TimePeriodManager._time_to_minutes(end_hour, end_minute)

                # 【优先级1】检查是否在时间段内（完全匹配）
                if TimePeriodManager._is_in_period(
                    current_minutes, start_minutes, end_minutes
                ):
                    matched_factor = target_factor
                    break  # 找到完全匹配，直接使用

                # 【优先级2】检查是否在进入过渡期
                is_in_enter, enter_progress = TimePeriodManager._is_in_transition_range(
                    current_minutes, start_minutes, transition_minutes, is_entering=True
                )

                if is_in_enter:
                    # 在进入过渡期：从1.0渐变到target_factor
                    if use_smooth_curve:
                        enter_progress = TimePeriodManager.ease_in_out_cubic(
                            enter_progress
                        )

                    transition_factor = 1.0 + (target_factor - 1.0) * enter_progress
                    transition_info = (
                        1.0,
                        target_factor,
                        enter_progress,
                        transition_factor,
                    )
                    continue  # 不break，继续检查其他时间段

                # 【优先级3】检查是否在离开过渡期
                is_in_exit, exit_progress = TimePeriodManager._is_in_transition_range(
                    current_minutes, end_minutes, transition_minutes, is_entering=False
                )

                if is_in_exit and not transition_info:
                    # 在离开过渡期：从target_factor渐变到1.0
                    if use_smooth_curve:
                        exit_progress = TimePeriodManager.ease_in_out_cubic(
                            exit_progress
                        )

                    transition_factor = (
                        target_factor + (1.0 - target_factor) * exit_progress
                    )
                    transition_info = (
                        target_factor,
                        1.0,
                        exit_progress,
                        transition_factor,
                    )
                    continue  # 不break，继续检查其他时间段

            except Exception as e:
                logger.error(f"[时间段计算] 处理时间段时发生错误: {period} - {e}")
                continue

        # 确定最终系数
        if matched_factor is not None:
            # 完全匹配
            final_factor = matched_factor
            if DEBUG_MODE:
                logger.info(
                    f"[时间段计算] 当前时间 {current_time.strftime('%H:%M')} "
                    f"匹配时间段，系数={final_factor:.2f}"
                )
        elif transition_info is not None:
            # 在过渡期
            from_factor, to_factor, progress, final_factor = transition_info
            if DEBUG_MODE:
                logger.info(
                    f"[时间段计算] 当前时间 {current_time.strftime('%H:%M')} "
                    f"在过渡期（{from_factor:.2f}→{to_factor:.2f}），"
                    f"进度={progress:.2f}，系数={final_factor:.2f}"
                )
        else:
            # 正常时段
            final_factor = 1.0
            if DEBUG_MODE:
                logger.info(
                    f"[时间段计算] 当前时间 {current_time.strftime('%H:%M')} "
                    f"无匹配时间段，使用默认系数=1.0"
                )

        # 应用最低/最高限制
        original_factor = final_factor
        final_factor = max(min_factor, min(max_factor, final_factor))

        if original_factor != final_factor and DEBUG_MODE:
            logger.info(
                f"[时间段计算] 系数已限制: {original_factor:.2f} → {final_factor:.2f} "
                f"(范围: {min_factor:.2f}-{max_factor:.2f})"
            )

        return final_factor

    # ========== 便捷方法 ==========

    @staticmethod
    def apply_time_factor_to_probability(
        base_probability: float,
        current_time: Optional[datetime] = None,
        periods_config: Optional[List[Dict]] = None,
        transition_minutes: int = 30,
        min_factor: float = 0.1,
        max_factor: float = 2.0,
        use_smooth_curve: bool = True,
    ) -> float:
        """
        将时间系数应用到基础概率上

        这是一个便捷方法，直接返回调整后的概率值

        Args:
            base_probability: 基础概率
            (其他参数同 calculate_time_factor)

        Returns:
            调整后的概率值
        """
        time_factor = TimePeriodManager.calculate_time_factor(
            current_time=current_time,
            periods_config=periods_config,
            transition_minutes=transition_minutes,
            min_factor=min_factor,
            max_factor=max_factor,
            use_smooth_curve=use_smooth_curve,
        )

        adjusted_probability = base_probability * time_factor

        # 确保概率在0-1之间
        adjusted_probability = max(0.0, min(1.0, adjusted_probability))

        return adjusted_probability
