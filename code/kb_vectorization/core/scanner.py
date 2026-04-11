"""
本地知识库全量向量化自动化系统 - 文件扫描模块
版本: v1.0
日期: 2026-03-01

本模块实现：
- 递归扫描目录
- 文件类型识别
- 业务分类
- 增量扫描
- 统计导出
"""

import csv
import fnmatch
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from .base import FileInfo, ScanResult
from .config import Config
from .utils import (
    setup_logger,
    get_file_hash,
    get_file_extension,
    format_file_size,
    ensure_directory,
)


class FileScanner:
    """文件扫描器"""

    def __init__(self, config: Config):
        """
        初始化文件扫描器

        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = setup_logger("scanner", config.log_dir, config.log_level)

        # 缓存
        self._exclude_cache: Set[str] = set()
        self._category_cache: Dict[str, str] = {}

    def scan(
        self,
        directories: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None
    ) -> ScanResult:
        """
        扫描目录

        Args:
            directories: 扫描目录列表，默认从配置读取
            file_types: 文件类型列表，默认从配置读取
            exclude_dirs: 排除目录列表，默认从配置读取

        Returns:
            扫描结果
        """
        # 获取参数
        directories = directories or self.config.get_scan_dirs()
        file_types = file_types or self.config.get_file_types()
        exclude_dirs = exclude_dirs or self.config.get_exclude_dirs()

        if not directories:
            self.logger.warning("未指定扫描目录")
            return ScanResult(0, 0, [], {})

        # 准备排除目录
        self._prepare_exclude_dirs(exclude_dirs)

        # 记录开始时间
        start_time = datetime.now()
        self.logger.info(f"开始扫描目录: {directories}")

        # 收集文件
        files: List[FileInfo] = []
        total_size = 0

        for directory in directories:
            if not os.path.isdir(directory):
                self.logger.warning(f"目录不存在: {directory}")
                continue

            scan_result = self._scan_directory(
                directory,
                file_types,
                recursive=self.config.is_recursive_scan()
            )
            files.extend(scan_result["files"])
            total_size += scan_result["total_size"]

        # 分类统计
        by_type: Dict[str, int] = {}
        by_category: Dict[str, int] = {}

        for file_info in files:
            # 按类型统计
            file_type = file_info.type
            by_type[file_type] = by_type.get(file_type, 0) + 1

            # 按分类统计
            category = file_info.category
            by_category[category] = by_category.get(category, 0) + 1

        # 计算扫描时间
        scan_time = (datetime.now() - start_time).total_seconds()

        self.logger.info(
            f"扫描完成: {len(files)} 个文件, "
            f"总大小 {format_file_size(total_size)}, "
            f"耗时 {scan_time:.2f} 秒"
        )

        return ScanResult(
            total_files=len(files),
            total_size=total_size,
            files=files,
            by_type=by_type,
            by_category=by_category,
            scan_time=scan_time
        )

    def _scan_directory(
        self,
        directory: str,
        file_types: List[str],
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        扫描单个目录

        Args:
            directory: 目录路径
            file_types: 文件类型列表
            recursive: 是否递归

        Returns:
            扫描结果字典
        """
        files: List[FileInfo] = []
        total_size = 0

        if recursive:
            # 递归扫描
            for root, dirs, filenames in os.walk(directory):
                # 过滤排除目录
                dirs[:] = [d for d in dirs if not self._should_exclude(os.path.join(root, d))]

                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    file_info = self._process_file(file_path, file_types)

                    if file_info:
                        files.append(file_info)
                        total_size += file_info.size
        else:
            # 只扫描顶层
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    file_info = self._process_file(file_path, file_types)

                    if file_info:
                        files.append(file_info)
                        total_size += file_info.size

        return {"files": files, "total_size": total_size}

    def _process_file(
        self,
        file_path: str,
        file_types: List[str]
    ) -> Optional[FileInfo]:
        """
        处理单个文件

        Args:
            file_path: 文件路径
            file_types: 文件类型列表

        Returns:
            文件信息对象，不符合条件返回 None
        """
        try:
            # 获取文件信息
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            file_name = os.path.basename(file_path)
            file_ext = get_file_extension(file_path)

            # 检查文件类型
            if file_types and file_ext not in file_types:
                return None

            # 检查文件大小
            max_size = self.config.get_max_file_size()
            if file_size > max_size:
                self.logger.debug(f"文件过大，跳过: {file_path}")
                return None

            # 检查是否为文本文件
            if not self._is_text_file(file_path):
                self.logger.debug(f"非文本文件，跳过: {file_path}")
                return None

            # 获取修改时间
            modified_time = datetime.fromtimestamp(file_stat.st_mtime)

            # 计算文件哈希（可选，用于增量检测）
            file_hash = None
            if file_size < 1024 * 1024:  # 小于 1MB 才计算哈希
                file_hash = get_file_hash(file_path)

            # 业务分类
            category = self.classify_file(file_path)

            return FileInfo(
                path=file_path,
                name=file_name,
                type=file_ext,
                category=category,
                size=file_size,
                modified_time=modified_time,
                is_valid=True,
                file_hash=file_hash
            )

        except Exception as e:
            self.logger.warning(f"处理文件失败 {file_path}: {e}")
            return None

    def _is_text_file(self, file_path: str) -> bool:
        """
        判断是否为文本文件

        Args:
            file_path: 文件路径

        Returns:
            是否为文本文件
        """
        # 常见文本文件扩展名
        text_extensions = {
            '.md', '.txt', '.csv', '.json', '.yaml', '.yml',
            '.xml', '.html', '.htm', '.css', '.js', '.ts',
            '.py', '.java', '.c', '.cpp', '.h', '.hpp',
            '.go', '.rs', '.sql', '.sh', '.bat', '.ps1',
            '.ini', '.cfg', '.conf', '.log'
        }

        ext = get_file_extension(file_path)
        if ext in text_extensions:
            return True

        # 尝试读取文件头部判断
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\x00' not in chunk
        except Exception:
            return False

    def _should_exclude(self, path: str) -> bool:
        """
        判断路径是否应该被排除

        Args:
            path: 路径

        Returns:
            是否应该排除
        """
        path_lower = path.lower()

        # 检查缓存
        if path_lower in self._exclude_cache:
            return True

        # 检查排除规则
        exclude_dirs = self.config.get_exclude_dirs()
        for exclude_pattern in exclude_dirs:
            # 支持通配符
            if fnmatch.fnmatch(path_lower, f"*{exclude_pattern.lower()}*"):
                self._exclude_cache.add(path_lower)
                return True

        return False

    def _prepare_exclude_dirs(self, exclude_dirs: List[str]) -> None:
        """
        准备排除目录缓存

        Args:
            exclude_dirs: 排除目录列表
        """
        self._exclude_cache.clear()

        for directory in self.config.get_scan_dirs():
            for exclude in exclude_dirs:
                exclude_path = os.path.join(directory, exclude).lower()
                self._exclude_cache.add(exclude_path)

    def classify_file(self, file_path: str) -> str:
        """
        根据文件路径分类

        Args:
            file_path: 文件路径

        Returns:
            分类名称
        """
        # 检查缓存
        if file_path in self._category_cache:
            return self._category_cache[file_path]

        # 使用配置的分类规则
        category = self.config.classify(file_path)

        # 缓存结果
        self._category_cache[file_path] = category
        return category

    def export_csv(
        self,
        scan_result: ScanResult,
        output_path: Optional[str] = None
    ) -> str:
        """
        导出扫描结果为 CSV

        Args:
            scan_result: 扫描结果
            output_path: 输出路径，默认使用配置中的统计目录

        Returns:
            CSV 文件路径
        """
        if output_path is None:
            stats_dir = self.config.get("stats.dir", "./data/stats")
            ensure_directory(stats_dir)
            output_path = os.path.join(stats_dir, "file_list.csv")

        try:
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow([
                    '路径', '文件名', '类型', '分类',
                    '大小(字节)', '修改时间', '是否有效'
                ])

                # 写入数据
                for file_info in scan_result.files:
                    writer.writerow([
                        file_info.path,
                        file_info.name,
                        file_info.type,
                        file_info.category,
                        file_info.size,
                        file_info.modified_time.strftime('%Y-%m-%d %H:%M:%S'),
                        file_info.is_valid
                    ])

            self.logger.info(f"CSV 导出成功: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"CSV 导出失败: {e}")
            raise

    def get_changes(
        self,
        old_files: List[FileInfo],
        new_files: List[FileInfo]
    ) -> Dict[str, List[FileInfo]]:
        """
        比较新旧文件列表，获取变化

        Args:
            old_files: 旧文件列表
            new_files: 新文件列表

        Returns:
            变化字典，包含 'added', 'modified', 'deleted', 'unchanged'
        """
        # 创建快速查找字典
        old_dict = {f.path: f for f in old_files}
        new_dict = {f.path: f for f in new_files}

        all_paths = set(old_dict.keys()) | set(new_dict.keys())

        changes = {
            "added": [],
            "modified": [],
            "deleted": [],
            "unchanged": []
        }

        for path in all_paths:
            old_file = old_dict.get(path)
            new_file = new_dict.get(path)

            if old_file is None:
                # 新增
                changes["added"].append(new_file)
            elif new_file is None:
                # 删除
                changes["deleted"].append(old_file)
            else:
                # 比较是否有变化
                if (old_file.file_hash and new_file.file_hash and
                    old_file.file_hash != new_file.file_hash):
                    changes["modified"].append(new_file)
                elif old_file.modified_time != new_file.modified_time:
                    changes["modified"].append(new_file)
                else:
                    changes["unchanged"].append(old_file)

        self.logger.info(
            f"文件变化检测: "
            f"新增 {len(changes['added'])}, "
            f"修改 {len(changes['modified'])}, "
            f"删除 {len(changes['deleted'])}"
        )

        return changes

    def clear_cache(self) -> None:
        """清除缓存"""
        self._exclude_cache.clear()
        self._category_cache.clear()


def quick_scan(
    directory: str,
    file_types: Optional[List[str]] = None,
    recursive: bool = True
) -> ScanResult:
    """
    快速扫描目录（使用默认配置）

    Args:
        directory: 扫描目录
        file_types: 文件类型
        recursive: 是否递归

    Returns:
        扫描结果
    """
    from .config import Config

    config = Config()
    config.set("scan.directories", [directory])
    config.set("scan.recursive", recursive)

    if file_types:
        config.set("scan.file_types", file_types)

    scanner = FileScanner(config)
    return scanner.scan()
