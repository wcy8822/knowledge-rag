"""
本地知识库全量向量化自动化系统 - 自动更新模块
版本: v1.0
日期: 2026-03-01

本模块实现：
- 文件系统监控
- 文件变化检测
- 自动向量化更新
- 定时任务调度
"""

import json
import os
import schedule
import threading
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from .base import FileEvent, FileInfo
from .config import Config
from .utils import setup_logger


@dataclass
class TaskResult:
    """任务执行结果"""
    task_name: str
    success: bool
    start_time: datetime
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None

    @property
    def duration(self) -> Optional[float]:
        """执行时长（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class FileUpdater:
    """文件更新器（文件监控 + 自动更新）"""

    def __init__(self, config, vectorizer=None, store=None):
        """
        初始化文件更新器

        Args:
            config: 配置对象
            vectorizer: 向量化器实例（可选）
            store: 向量存储实例（可选）
        """
        self.config = config
        self.vectorizer = vectorizer
        self.store = store
        self.logger = setup_logger("updater", config.log_dir, config.log_level)

        # 状态
        self._running = False
        self._observer = None
        self._scheduler_thread = None
        self._event_queue = []

        # 文件缓存
        self._file_cache: Dict[str, FileInfo] = {}
        self._cache_file = os.path.join(
            config.get("stats.dir", "./data/stats"),
            "file_cache.json"
        )

        # 事件处理器
        self._event_handlers = {
            "created": self._on_created,
            "modified": self._on_modified,
            "deleted": self._on_deleted,
            "moved": self._on_moved
        }

        # 任务回调
        self._task_callbacks = {}

        # 加载缓存
        self._load_cache()

    def start_monitor(self, directories: Optional[List[str]] = None) -> None:
        """
        启动文件监控

        Args:
            directories: 监控目录列表，默认从配置读取
        """
        if self._running:
            self.logger.warning("监控已在运行")
            return

        directories = directories or self.config.get_scan_dirs()
        if not directories:
            self.logger.warning("未指定监控目录")
            return

        # 初始化 watchdog
        self._init_watchdog(directories)

        # 启动定时任务
        if self.config.get("monitor.enable_schedule", True):
            self._start_scheduler()

        self._running = True
        self.logger.info(f"文件监控已启动: {directories}")

    def stop_monitor(self) -> None:
        """停止文件监控"""
        if not self._running:
            return

        # 停止 watchdog
        if self._observer:
            self._observer.stop()
            self._observer.join()

        # 停止定时任务
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            schedule.clear()
            self._scheduler_thread.join(timeout=5)

        self._running = False
        self.logger.info("文件监控已停止")

    def _init_watchdog(self, directories: List[str]) -> None:
        """
        初始化 watchdog

        Args:
            directories: 监控目录列表
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class EventHandler(FileSystemEventHandler):
                """文件事件处理器"""

                def __init__(self, updater):
                    self.updater = updater

                def on_created(self, event):
                    if not event.is_directory:
                        self.updater._queue_event(
                            FileEvent("created", event.src_path)
                        )

                def on_modified(self, event):
                    if not event.is_directory:
                        self.updater._queue_event(
                            FileEvent("modified", event.src_path)
                        )

                def on_deleted(self, event):
                    if not event.is_directory:
                        self.updater._queue_event(
                            FileEvent("deleted", event.src_path)
                        )

                def on_moved(self, event):
                    if not event.is_directory:
                        self.updater._queue_event(
                            FileEvent("moved", event.src_path,
                                    dest_path=event.dest_path)
                        )

            # 创建观察者
            self._observer = Observer()

            # 为每个目录添加事件处理器
            handler = EventHandler(self)
            for directory in directories:
                if os.path.isdir(directory):
                    self._observer.schedule(handler, directory, recursive=True)
                    self.logger.debug(f"监控目录: {directory}")

            # 启动观察者
            self._observer.start()

            # 启动事件处理线程
            self._start_event_processor()

        except ImportError:
            self.logger.error("Watchdog 未安装，文件监控功能不可用")
        except Exception as e:
            self.logger.error(f"初始化 watchdog 失败: {e}")

    def _start_event_processor(self) -> None:
        """启动事件处理线程"""
        def process_events():
            while self._running:
                if self._event_queue:
                    event = self._event_queue.pop(0)
                    self._handle_event(event)
                time.sleep(0.1)

        thread = threading.Thread(target=process_events, daemon=True)
        thread.start()

    def _queue_event(self, event: FileEvent) -> None:
        """
        将事件加入队列

        Args:
            event: 文件事件
        """
        # 延迟处理，避免频繁触发
        delay = self.config.get("monitor.event_delay", 2)
        time.sleep(delay)

        # 去重：如果队列中已有该文件的同类事件，替换
        for i, queued in enumerate(self._event_queue):
            if (queued.event_type == event.event_type and
                queued.src_path == event.src_path):
                self._event_queue[i] = event
                return

        self._event_queue.append(event)

    def _handle_event(self, event: FileEvent) -> None:
        """
        处理文件事件

        Args:
            event: 文件事件
        """
        handler = self._event_handlers.get(event.event_type)
        if handler:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"处理事件失败 {event}: {e}")

    def _on_created(self, event: FileEvent) -> None:
        """
        处理文件创建事件

        Args:
            event: 文件事件
        """
        self.logger.info(f"文件创建: {event.src_path}")

        # 检查是否需要处理
        if not self._should_process_file(event.src_path):
            return

        # 更新向量库
        self._update_file(event.src_path)

    def _on_modified(self, event: FileEvent) -> None:
        """
        处理文件修改事件

        Args:
            event: 文件事件
        """
        self.logger.info(f"文件修改: {event.src_path}")

        if not self._should_process_file(event.src_path):
            return

        # 删除旧向量，重新向量化
        self._update_file(event.src_path)

    def _on_deleted(self, event: FileEvent) -> None:
        """
        处理文件删除事件

        Args:
            event: 文件事件
        """
        self.logger.info(f"文件删除: {event.src_path}")

        # 标记向量失效
        if self.store:
            count = self.store.delete_by_file(event.src_path)
            self.logger.debug(f"删除 {count} 个向量")

        # 从缓存中移除
        if event.src_path in self._file_cache:
            del self._file_cache[event.src_path]
            self._save_cache()

    def _on_moved(self, event: FileEvent) -> None:
        """
        处理文件移动事件

        Args:
            event: 文件事件
        """
        self.logger.info(f"文件移动: {event.src_path} -> {event.dest_path}")

        # 更新元数据中的路径
        if self.store:
            # Chroma 支持更新元数据
            # FAISS 需要重建，这里只做简单处理
            pass

    def _should_process_file(self, file_path: str) -> bool:
        """
        判断是否需要处理该文件

        Args:
            file_path: 文件路径

        Returns:
            是否需要处理
        """
        # 检查文件类型
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.config.get_file_types():
            return False

        # 检查文件大小
        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.config.get_max_file_size():
                return False
        except Exception:
            return False

        return True

    def _update_file(self, file_path: str) -> None:
        """
        更新文件向量

        Args:
            file_path: 文件路径
        """
        if not self.vectorizer or not self.store:
            return

        try:
            # 删除旧向量
            self.store.delete_by_file(file_path)

            # 向量化新文件
            chunks = self.vectorizer.vectorize_file(file_path)

            # 添加到存储
            if chunks:
                self.store.add_vectors(chunks)
                self.logger.info(f"文件 {file_path} 向量化完成，{len(chunks)} 个块")

        except Exception as e:
            self.logger.error(f"更新文件向量失败 {file_path}: {e}")

    # ===== 定时任务 =====

    def _start_scheduler(self) -> None:
        """启动定时任务调度器"""
        schedule_config = self.config.get("monitor.schedule", {})

        # 注册定时任务
        if "full_validation_time" in schedule_config:
            time_str = schedule_config["full_validation_time"]
            schedule.every().day.at(time_str).do(self._full_validation)
            self.logger.info(f"注册定时任务: 全量校验 {time_str}")

        if "cleanup_time" in schedule_config:
            time_str = schedule_config["cleanup_time"]
            schedule.every().day.at(time_str).do(self._cleanup_vectors)
            self.logger.info(f"注册定时任务: 清理失效向量 {time_str}")

        if "report_time" in schedule_config:
            time_str = schedule_config["report_time"]
            schedule.every().day.at(time_str).do(self._generate_report)
            self.logger.info(f"注册定时任务: 生成报告 {time_str}")

        # 启动调度器线程
        def run_scheduler():
            while self._running:
                schedule.run_pending()
                time.sleep(60)

        self._scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self._scheduler_thread.start()

    def run_scheduled_tasks(self) -> None:
        """手动执行所有定时任务"""
        self.logger.info("执行定时任务...")

        # 全量校验
        self._full_validation()

        # 清理失效向量
        self._cleanup_vectors()

        # 生成报告
        self._generate_report()

    def _full_validation(self) -> TaskResult:
        """
        全量校验

        Returns:
            任务结果
        """
        task_name = "全量校验"
        self.logger.info(f"开始执行任务: {task_name}")

        result = TaskResult(task_name=task_name, success=True, start_time=datetime.now())

        try:
            from .scanner import FileScanner

            scanner = FileScanner(self.config)
            directories = self.config.get_scan_dirs()

            if not directories:
                self.logger.warning("未配置扫描目录")
                result.success = False
                result.error = "未配置扫描目录"
                result.end_time = datetime.now()
                return result

            # 扫描当前文件
            scan_result = scanner.scan()
            current_files = {f.path: f for f in scan_result.files}

            # 比较缓存
            changes = scanner.get_changes(
                list(self._file_cache.values()),
                list(current_files.values())
            )

            # 处理变化
            stats = {
                "added": len(changes["added"]),
                "modified": len(changes["modified"]),
                "deleted": len(changes["deleted"])
            }

            # 更新缓存
            self._file_cache = current_files
            self._save_cache()

            result.stats = stats
            self.logger.info(f"全量校验完成: {stats}")

        except Exception as e:
            result.success = False
            result.error = str(e)
            self.logger.error(f"全量校验失败: {e}")

        result.end_time = datetime.now()
        return result

    def _cleanup_vectors(self) -> TaskResult:
        """
        清理失效向量

        Returns:
            任务结果
        """
        task_name = "清理失效向量"
        self.logger.info(f"开始执行任务: {task_name}")

        result = TaskResult(task_name=task_name, success=True, start_time=datetime.now())

        try:
            if not self.store:
                self.logger.warning("向量存储未初始化")
                result.success = False
                result.error = "向量存储未初始化"
                result.end_time = datetime.now()
                return result

            # 获取所有存储的文件路径
            stored_files = set()
            for meta in self.store.metadata_store._metadata.values():
                stored_files.add(meta["file_path"])

            # 获取当前存在的文件
            current_files = set(self._file_cache.keys())

            # 找出失效文件（已删除）
            invalid_files = stored_files - current_files

            # 删除失效向量
            deleted_count = 0
            for file_path in invalid_files:
                count = self.store.delete_by_file(file_path)
                deleted_count += count
                self.logger.debug(f"删除失效向量: {file_path} ({count}个)")

            result.stats = {
                "invalid_files": len(invalid_files),
                "deleted_vectors": deleted_count
            }

            self.logger.info(f"清理失效向量完成: {result.stats}")

        except Exception as e:
            result.success = False
            result.error = str(e)
            self.logger.error(f"清理失效向量失败: {e}")

        result.end_time = datetime.now()
        return result

    def _generate_report(self) -> TaskResult:
        """
        生成统计报告

        Returns:
            任务结果
        """
        task_name = "生成报告"
        self.logger.info(f"开始执行任务: {task_name}")

        result = TaskResult(task_name=task_name, success=True, start_time=datetime.now())

        try:
            # 收集统计信息
            stats = {
                "generated_at": datetime.now().isoformat(),
                "total_files": len(self._file_cache),
                "store_stats": self.store.get_stats() if self.store else {},
                "config": {
                    "scan_dirs": self.config.get_scan_dirs(),
                    "file_types": self.config.get_file_types(),
                    "batch_size": self.config.batch_size,
                    "vector_dim": self.config.vector_dim
                }
            }

            # 保存报告
            report_dir = os.path.join(
                self.config.get("stats.dir", "./data/stats"),
                self.config.get("stats.daily_reports_dir", "daily_reports")
            )
            os.makedirs(report_dir, exist_ok=True)

            report_file = os.path.join(
                report_dir,
                f"report_{datetime.now().strftime('%Y%m%d')}.json"
            )

            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)

            result.stats = {"report_file": report_file}
            self.logger.info(f"报告已生成: {report_file}")

        except Exception as e:
            result.success = False
            result.error = str(e)
            self.logger.error(f"生成报告失败: {e}")

        result.end_time = datetime.now()
        return result

    # ===== 缓存管理 =====

    def _load_cache(self) -> None:
        """加载文件缓存"""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._file_cache = {
                        k: FileInfo.from_dict(v)
                        for k, v in data.get("files", {}).items()
                    }
                self.logger.debug(f"加载文件缓存: {len(self._file_cache)} 个文件")
            except Exception as e:
                self.logger.warning(f"加载缓存失败: {e}")

    def _save_cache(self) -> None:
        """保存文件缓存"""
        try:
            data = {
                "updated_at": datetime.now().isoformat(),
                "files": {
                    k: v.to_dict()
                    for k, v in self._file_cache.items()
                }
            }

            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"保存缓存失败: {e}")

    def register_task_callback(self, task_name: str, callback: Callable[[TaskResult], None]) -> None:
        """
        注册任务回调

        Args:
            task_name: 任务名称
            callback: 回调函数
        """
        self._task_callbacks[task_name] = callback

    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running


# 快捷函数
def start_updater(config, vectorizer=None, store=None) -> FileUpdater:
    """
    启动文件更新器

    Args:
        config: 配置对象
        vectorizer: 向量化器实例
        store: 向量存储实例

    Returns:
        文件更新器实例
    """
    updater = FileUpdater(config, vectorizer, store)
    updater.start_monitor()
    return updater


__all__ = [
    # 数据类
    "TaskResult",
    # 更新器
    "FileUpdater",
    # 快捷函数
    "start_updater",
]
