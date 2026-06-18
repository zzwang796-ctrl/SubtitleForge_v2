#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SubtitleForge v2 - 统一日志系统

提供跨平台的日志管理，支持：
- 多级别日志（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- 文件和控制台双输出
- 自动日志轮转
- 模块级日志器隔离
- UTF-8 编码支持（兼容 Windows GBK 终端）
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading


# 全局日志锁，确保线程安全
_log_lock = threading.Lock()

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# 默认日志配置
DEFAULT_CONFIG = {
    "level": "INFO",
    "log_dir": None,  # None 表示使用项目目录下的 logs 文件夹
    "max_bytes": 10 * 1024 * 1024,  # 10 MB
    "backup_count": 5,
    "console_encoding": "utf-8",
    "file_encoding": "utf-8",
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
}

# 全局配置
_config = DEFAULT_CONFIG.copy()
_root_logger = None
_initialized = False


def _get_log_dir() -> Path:
    """获取日志目录路径"""
    if _config["log_dir"]:
        log_dir = Path(_config["log_dir"])
    else:
        # 使用项目目录下的 logs 文件夹
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent
        log_dir = project_root / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _get_console_handler_formatter() -> tuple:
    """获取控制台处理器和格式化器"""
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)

    # 检测终端编码
    if sys.platform == "win32":
        # Windows 终端尝试使用 UTF-8，如果失败则回退
        try:
            import locale
            encoding = locale.getpreferredencoding(False)
            if encoding.lower() in ["gbk", "cp936", "windows-1252"]:
                # Windows 中文环境使用 GBK
                console_handler.encoding = "gbk"
            else:
                console_handler.encoding = "utf-8"
        except Exception:
            console_handler.encoding = "utf-8"
    else:
        console_handler.encoding = "utf-8"

    # 格式化器（控制台使用简洁格式）
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)

    return console_handler, console_formatter


def _get_file_handler_formatter(log_dir: Path) -> tuple:
    """获取文件处理器和格式化器"""
    # 生成日志文件名
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"subtitleforge_{timestamp}.log"

    # 使用 RotatingFileHandler 实现日志轮转
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=_config["max_bytes"],
        backupCount=_config["backup_count"],
        encoding=_config["file_encoding"],
        delay=True  # 延迟打开文件
    )

    # 文件格式化器（包含完整信息）
    file_formatter = logging.Formatter(
        _config["format"],
        datefmt=_config["date_format"]
    )
    file_handler.setFormatter(file_formatter)

    return file_handler, file_formatter


def setup(
    level: str = "INFO",
    log_dir: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    初始化全局日志系统

    Args:
        level: 日志级别，可选 DEBUG/INFO/WARNING/ERROR/CRITICAL
        log_dir: 日志文件目录，None 表示使用默认目录
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量

    Returns:
        配置好的根日志器

    Example:
        >>> from logging_setup import setup, get_logger
        >>> setup(level="DEBUG", log_dir="./logs")
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    global _config, _root_logger, _initialized

    with _log_lock:
        if _initialized:
            return _root_logger

        # 更新配置
        _config.update({
            "level": level.upper(),
            "log_dir": log_dir,
            "max_bytes": max_bytes,
            "backup_count": backup_count,
        })

        # 获取根日志器
        root_logger = logging.getLogger("subtitleforge")
        root_logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        root_logger.handlers.clear()

        # 获取日志目录
        log_dir_path = _get_log_dir()

        # 添加控制台处理器
        console_handler, _ = _get_console_handler_formatter()
        console_handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        root_logger.addHandler(console_handler)

        # 添加文件处理器
        try:
            file_handler, _ = _get_file_handler_formatter(log_dir_path)
            file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
            root_logger.addHandler(file_handler)
            root_logger.debug(f"日志文件: {log_dir_path / 'subtitleforge_*.log'}")
        except Exception as e:
            console_handler.setLevel(logging.WARNING)
            root_logger.warning(f"无法创建日志文件: {e}")

        # 禁止传播到根日志器（避免重复输出）
        root_logger.propagate = False

        _root_logger = root_logger
        _initialized = True

        root_logger.info("=" * 50)
        root_logger.info("SubtitleForge v2 日志系统已初始化")
        root_logger.info(f"日志级别: {level.upper()}")
        root_logger.info(f"日志目录: {log_dir_path}")
        root_logger.info("=" * 50)

        return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器

    Args:
        name: 日志器名称，通常使用 __name__

    Returns:
        配置好的日志器

    Example:
        >>> from logging_setup import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("This is an info message")
        >>> logger.error("This is an error message", exc_info=True)
    """
    global _root_logger, _initialized

    # 确保日志系统已初始化
    if not _initialized:
        setup()

    # 创建模块级日志器
    logger = logging.getLogger(f"subtitleforge.{name}")

    return logger


def set_level(level: str) -> None:
    """
    动态设置日志级别

    Args:
        level: 日志级别，DEBUG/INFO/WARNING/ERROR/CRITICAL
    """
    global _root_logger, _config

    if _root_logger is None:
        return

    level_value = LOG_LEVELS.get(level.upper(), logging.INFO)
    _root_logger.setLevel(level_value)

    # 同时设置所有 handler 的级别
    for handler in _root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.DEBUG)  # 文件始终记录所有
        else:
            handler.setLevel(level_value)

    _config["level"] = level.upper()


def add_file_handler(
    filepath: str,
    level: str = "INFO",
    format_str: Optional[str] = None
) -> logging.FileHandler:
    """
    添加额外的文件处理器

    Args:
        filepath: 日志文件路径
        level: 日志级别
        format_str: 自定义格式字符串

    Returns:
        创建的文件处理器
    """
    global _root_logger

    if _root_logger is None:
        setup()

    handler = logging.FileHandler(filepath, encoding="utf-8")
    handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))

    if format_str:
        formatter = logging.Formatter(format_str)
    else:
        formatter = logging.Formatter(_config["format"])

    handler.setFormatter(formatter)
    _root_logger.addHandler(handler)

    return handler


def shutdown() -> None:
    """
    关闭日志系统，刷新所有处理器
    """
    global _root_logger

    if _root_logger:
        for handler in _root_logger.handlers:
            handler.flush()
            handler.close()
        _root_logger.handlers.clear()


# ============================================================
# 便捷函数：直接记录日志
# ============================================================

def debug(message: str, *args, **kwargs) -> None:
    """记录 DEBUG 级别日志"""
    get_logger("quick").debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs) -> None:
    """记录 INFO 级别日志"""
    get_logger("quick").info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs) -> None:
    """记录 WARNING 级别日志"""
    get_logger("quick").warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs) -> None:
    """记录 ERROR 级别日志"""
    get_logger("quick").error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs) -> None:
    """记录 CRITICAL 级别日志"""
    get_logger("quick").critical(message, *args, **kwargs)


# ============================================================
# 模块自检
# ============================================================

if __name__ == "__main__":
    # 测试日志系统
    setup(level="DEBUG")

    logger = get_logger(__name__)

    logger.debug("这是 DEBUG 消息")
    logger.info("这是 INFO 消息")
    logger.warning("这是 WARNING 消息")
    logger.error("这是 ERROR 消息")
    logger.critical("这是 CRITICAL 消息")

    # 测试便捷函数
    info("使用便捷函数记录 INFO 消息")
    error("使用便捷函数记录 ERROR 消息")

    # 测试异常记录
    try:
        raise ValueError("测试异常")
    except Exception:
        logger.exception("捕获到异常")

    print("\n日志系统测试完成！")
    print(f"日志文件位置: {_get_log_dir()}")
