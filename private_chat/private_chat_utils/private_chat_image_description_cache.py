"""
图片描述缓存模块
将图片URL与其AI生成的文字描述进行本地缓存，避免重复调用AI转换同一张图片。

核心设计原则：
1. 查找时逐行读取文件，不一次性加载到内存
2. 写入时使用追加模式，直接往文件末尾写
3. 超过限制时移除最旧的条目
4. 所有会话共享同一份缓存（不需要会话隔离）

文件格式：JSONL（每行一个JSON对象）
{"u":"图片URL","d":"文字描述","t":时间戳}

作者: Him666233
版本: v1.2.1
"""

import json
import os
import time
import tempfile
from pathlib import Path
from typing import Optional
from astrbot.api import logger

# 详细日志开关
DEBUG_MODE: bool = False


class ImageDescriptionCache:
    """
    图片描述缓存器

    主要功能：
    1. 根据图片URL查找已缓存的文字描述（逐行扫描，不全量加载）
    2. 将新的URL-描述对追加到缓存文件
    3. 超过最大条目限制时自动清理最旧的记录
    4. 提供清空缓存的方法
    """

    def __init__(self, data_dir: str, max_entries: int = 500, enabled: bool = False):
        """
        初始化图片描述缓存

        Args:
            data_dir: 数据存储目录
            max_entries: 最大缓存条目数（正数）
            enabled: 是否启用缓存
        """
        self._enabled = enabled
        self._max_entries = max(10, min(max_entries, 10000))  # 硬限制10-10000
        self._cache_dir = Path(data_dir) / "image_cache"
        self._cache_file = self._cache_dir / "descriptions.jsonl"
        self._entry_count: int = 0  # 当前缓存条目计数（内存中维护）
        self._initialized = False

        if self._enabled:
            self._init_storage()

    def _init_storage(self):
        """初始化存储目录和计数"""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            # 通过统计文件行数初始化计数器（不加载内容）
            self._entry_count = self._count_lines()
            self._initialized = True
            logger.info(
                f"[图片缓存] 已初始化，当前缓存 {self._entry_count} 条，"
                f"上限 {self._max_entries} 条，"
                f"文件: {self._cache_file}"
            )
        except Exception as e:
            logger.error(f"[图片缓存] 初始化失败: {e}")
            self._initialized = False

    def _count_lines(self) -> int:
        """
        统计缓存文件的行数（不加载内容到内存）

        Returns:
            文件行数
        """
        if not self._cache_file.exists():
            return 0
        count = 0
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                for _ in f:
                    count += 1
        except Exception:
            count = 0
        return count

    @property
    def enabled(self) -> bool:
        return self._enabled and self._initialized

    @property
    def entry_count(self) -> int:
        return self._entry_count

    def lookup(self, url: str) -> Optional[str]:
        """
        查找URL对应的缓存描述（逐行扫描，找到即停，不全量加载）

        Args:
            url: 图片URL

        Returns:
            缓存的文字描述，未找到返回None
        """
        if not self.enabled or not url:
            return None

        if not self._cache_file.exists():
            return None

        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("u") == url:
                            desc = entry.get("d", "")
                            if desc:
                                if DEBUG_MODE:
                                    logger.info(
                                        f"[图片缓存] 命中缓存: {url[:80]}... -> {desc[:50]}..."
                                    )
                                return desc
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            logger.warning(f"[图片缓存] 查找时发生错误: {e}")

        return None

    def save(self, url: str, description: str):
        """
        保存URL-描述对到缓存（追加写入，不读取现有内容）

        如果超过最大条目限制，会自动触发清理。

        Args:
            url: 图片URL
            description: AI生成的文字描述
        """
        if not self.enabled or not url or not description:
            return

        try:
            entry = {
                "u": url,
                "d": description,
                "t": int(time.time()),
            }
            # 追加模式写入
            with open(self._cache_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._entry_count += 1

            if DEBUG_MODE:
                logger.info(
                    f"[图片缓存] 已保存: {url[:80]}... ({self._entry_count}/{self._max_entries})"
                )

            # 超过限制时清理
            if self._entry_count > self._max_entries:
                self._cleanup_oldest()

        except Exception as e:
            logger.warning(f"[图片缓存] 保存时发生错误: {e}")

    def _cleanup_oldest(self):
        """
        清理最旧的条目，保留最新的 max_entries * 0.8 条

        采用逐行读写方式：读取原文件 -> 跳过最旧的N行 -> 写入临时文件 -> 替换原文件
        """
        try:
            if not self._cache_file.exists():
                return

            # 计算需要保留的条目数（保留80%，给新条目留空间）
            keep_count = int(self._max_entries * 0.8)
            skip_count = self._entry_count - keep_count

            if skip_count <= 0:
                return

            logger.info(
                f"[图片缓存] 缓存条目 ({self._entry_count}) 超过上限 ({self._max_entries})，"
                f"清理最旧的 {skip_count} 条，保留 {keep_count} 条"
            )

            # 使用临时文件避免数据丢失
            temp_fd, temp_path = tempfile.mkstemp(
                dir=str(self._cache_dir), suffix=".tmp"
            )

            try:
                skipped = 0
                written = 0
                with open(self._cache_file, "r", encoding="utf-8") as src:
                    with os.fdopen(temp_fd, "w", encoding="utf-8") as dst:
                        for line in src:
                            if skipped < skip_count:
                                skipped += 1
                                continue
                            dst.write(line)
                            written += 1

                # 原子替换原文件（os.replace 跨平台，Windows/Linux/macOS 均可用）
                os.replace(temp_path, str(self._cache_file))

                self._entry_count = written
                logger.info(f"[图片缓存] 清理完成，当前缓存 {self._entry_count} 条")

            except Exception as e:
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                raise e

        except Exception as e:
            logger.error(f"[图片缓存] 清理旧条目时发生错误: {e}")

    def clear(self) -> bool:
        """
        清空所有缓存

        Returns:
            True=成功，False=失败
        """
        try:
            if self._cache_file.exists():
                self._cache_file.unlink()
            self._entry_count = 0
            logger.info("[图片缓存] 缓存已清空")
            return True
        except Exception as e:
            logger.error(f"[图片缓存] 清空缓存失败: {e}")
            return False

    def get_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            包含统计信息的字典
        """
        file_size = 0
        try:
            if self._cache_file.exists():
                file_size = self._cache_file.stat().st_size
        except Exception:
            pass

        return {
            "enabled": self._enabled,
            "initialized": self._initialized,
            "entry_count": self._entry_count,
            "max_entries": self._max_entries,
            "file_size_bytes": file_size,
            "file_path": str(self._cache_file),
        }
