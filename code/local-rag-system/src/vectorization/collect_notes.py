#!/usr/bin/env python3
"""
文件收集模块
扫描全局笔记位置，生成详细的文件清单，用于后续向量化处理
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.vectorization.utils import (
    calculate_file_hash,
    is_valid_note_file,
    save_json_report,
    create_file_metadata,
    generate_timestamp,
    generate_report_filename,
    ensure_directory_exists,
    format_bytes,
    print_section_header,
    print_subsection,
    print_progress
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NotesCollector:
    """
    笔记文件收集器

    功能：
    - 扫描多个笔记位置
    - 验证和过滤文件
    - 去重处理
    - 生成详细的收集报告
    """

    def __init__(self, output_dir: str = "logs"):
        """
        初始化收集器

        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = output_dir
        ensure_directory_exists(output_dir)

        # 扫描位置（按优先级排列）
        self.scan_locations = [
            "/Users/didi/Downloads/panth",  # 主要笔记位置
            "/Users/didi/sync",             # 同步目录
            os.path.expanduser("~/Documents"),  # 文档目录
            os.path.expanduser("~/Desktop"),    # 桌面
        ]

        # 收集统计数据
        self.stats = {
            "timestamp": generate_timestamp(),
            "total_files_found": 0,
            "valid_notes": 0,
            "skipped_files": 0,
            "total_size_bytes": 0,
            "files_by_format": defaultdict(int),
            "files_by_location": defaultdict(int),
            "duplicates_removed": 0,
            "errors": []
        }

        # 文件列表（用于去重）
        self.file_checksums = {}  # checksum -> file_info
        self.files = []  # 最终的有效文件列表

    def scan_location(self, location: str) -> List[Path]:
        """
        扫描单个位置的所有可能的笔记文件

        Args:
            location: 扫描位置

        Returns:
            找到的文件路径列表
        """
        files = []

        if not os.path.exists(location):
            logger.warning(f"位置不存在: {location}")
            return files

        try:
            for root, dirs, filenames in os.walk(location):
                # 跳过某些目录以加快扫描
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for filename in filenames:
                    file_path = Path(root) / filename
                    self.stats["total_files_found"] += 1

                    # 检查是否为有效笔记文件
                    if is_valid_note_file(str(file_path)):
                        files.append(file_path)
                    else:
                        self.stats["skipped_files"] += 1

        except Exception as e:
            error_msg = f"扫描位置失败 {location}: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)

        return files

    def collect_all_notes(self) -> List[Dict[str, Any]]:
        """
        收集所有笔记文件

        Returns:
            收集到的文件列表（已去重和排序）
        """
        logger.info("=" * 60)
        logger.info("🔍 开始收集笔记文件")
        logger.info("=" * 60)

        all_files = []

        # 1. 扫描所有位置
        logger.info(f"\n📂 扫描 {len(self.scan_locations)} 个位置...")

        for location in self.scan_locations:
            logger.info(f"  扫描: {location}")
            location_files = self.scan_location(location)
            if location_files:
                logger.info(f"    ✅ 找到 {len(location_files)} 个文件")
                all_files.extend(location_files)
            else:
                logger.info(f"    ⚠️  未找到文件")

        logger.info(f"\n📊 第一阶段统计:")
        logger.info(f"  总扫描: {self.stats['total_files_found']} 文件")
        logger.info(f"  有效笔记: {len(all_files)} 文件")
        logger.info(f"  跳过: {self.stats['skipped_files']} 文件")

        # 2. 去重处理
        logger.info(f"\n🔄 去重处理...")

        unique_files = []
        checksums_seen = set()

        for file_path in all_files:
            try:
                # 计算文件哈希
                checksum = calculate_file_hash(str(file_path))

                if checksum == "error":
                    error_msg = f"无法计算哈希: {file_path}"
                    logger.warning(error_msg)
                    self.stats["errors"].append(error_msg)
                    continue

                # 检查是否重复
                if checksum in checksums_seen:
                    logger.debug(f"  重复文件（跳过）: {file_path.name}")
                    self.stats["duplicates_removed"] += 1
                else:
                    unique_files.append(file_path)
                    checksums_seen.add(checksum)

            except Exception as e:
                error_msg = f"处理文件失败 {file_path}: {e}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)

        logger.info(f"  ✅ 去重完成: {len(unique_files)} 个唯一文件")
        if self.stats["duplicates_removed"] > 0:
            logger.info(f"  📌 移除重复: {self.stats['duplicates_removed']} 个")

        # 3. 创建详细的文件元数据
        logger.info(f"\n📝 创建文件元数据...")

        for idx, file_path in enumerate(unique_files):
            try:
                # 创建文件元数据
                metadata = create_file_metadata(str(file_path), file_id=f"note_{idx+1:05d}")

                # 更新统计数据
                self.stats["valid_notes"] += 1
                self.stats["total_size_bytes"] += metadata["size_bytes"]

                # 记录格式统计
                fmt = metadata["format"].lower()
                self.stats["files_by_format"][fmt] += 1

                # 记录位置统计
                for location in self.scan_locations:
                    if location in metadata["path"]:
                        self.stats["files_by_location"][location] += 1
                        break

                self.files.append(metadata)

            except Exception as e:
                error_msg = f"创建元数据失败 {file_path}: {e}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)

        logger.info(f"  ✅ 元数据创建完成: {len(self.files)} 个文件")

        # 4. 按文件名排序（提高可重复性）
        self.files.sort(key=lambda x: x["path"])

        logger.info(f"\n✅ 收集完成")

        return self.files

    def generate_report(self) -> Dict[str, Any]:
        """
        生成详细的收集报告

        Returns:
            报告字典
        """
        # 转换统计数据为可序列化格式
        stats_dict = {
            "timestamp": self.stats["timestamp"],
            "total_files_found": self.stats["total_files_found"],
            "valid_notes": self.stats["valid_notes"],
            "skipped_files": self.stats["skipped_files"],
            "duplicates_removed": self.stats["duplicates_removed"],
            "total_size_bytes": self.stats["total_size_bytes"],
            "total_size_human": format_bytes(self.stats["total_size_bytes"]),
            "files_by_format": dict(self.stats["files_by_format"]),
            "files_by_location": dict(self.stats["files_by_location"]),
            "scan_locations": self.scan_locations,
            "errors": self.stats["errors"]
        }

        report = {
            "metadata": {
                "report_type": "notes_collection",
                "version": "1.0",
                "generated_at": generate_timestamp(),
                "generator": "NotesCollector"
            },
            "summary": stats_dict,
            "files": self.files
        }

        return report

    def save_report(self) -> str:
        """
        保存收集报告到文件

        Returns:
            保存的报告文件路径
        """
        report = self.generate_report()

        # 生成报告文件名
        report_filename = generate_report_filename("collection_report", "json")
        report_path = os.path.join(self.output_dir, report_filename)

        # 保存报告
        success = save_json_report(report, report_path)

        if success:
            logger.info(f"✅ 报告已保存: {report_path}")
            return report_path
        else:
            logger.error(f"❌ 报告保存失败: {report_path}")
            return None

    def print_summary(self):
        """
        打印收集摘要
        """
        print_section_header("📊 笔记收集摘要", width=70)

        print(f"\n📈 总体统计:")
        print(f"  • 总扫描文件: {self.stats['total_files_found']:,}")
        print(f"  • 有效笔记: {self.stats['valid_notes']:,}")
        print(f"  • 跳过: {self.stats['skipped_files']:,}")
        print(f"  • 去重移除: {self.stats['duplicates_removed']}")
        print(f"  • 总大小: {format_bytes(self.stats['total_size_bytes'])}")

        if self.stats['files_by_format']:
            print(f"\n📁 按格式统计:")
            for fmt, count in sorted(self.stats['files_by_format'].items(), key=lambda x: -x[1]):
                print(f"  • .{fmt}: {count}")

        if self.stats['files_by_location']:
            print(f"\n📍 按位置统计:")
            for location, count in sorted(self.stats['files_by_location'].items(), key=lambda x: -x[1]):
                loc_name = os.path.basename(location) or location
                print(f"  • {loc_name}: {count}")

        if self.stats['errors']:
            print(f"\n⚠️  错误和警告 ({len(self.stats['errors'])})")
            for error in self.stats['errors'][:5]:  # 只显示前5个
                print(f"  • {error}")
            if len(self.stats['errors']) > 5:
                print(f"  ... 及 {len(self.stats['errors']) - 5} 个更多错误")

        print(f"\n✅ 准备向量化: {self.stats['valid_notes']} 个笔记文件")
        print_section_header("", width=70)


def main():
    """
    主函数：执行笔记收集
    """
    try:
        # 创建收集器
        collector = NotesCollector(output_dir="logs")

        # 收集笔记
        files = collector.collect_all_notes()

        # 保存报告
        report_path = collector.save_report()

        # 打印摘要
        collector.print_summary()

        # 返回成功状态
        return {
            "success": True,
            "files_collected": len(files),
            "report_path": report_path,
            "files": files
        }

    except Exception as e:
        logger.error(f"❌ 收集失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    result = main()

    if result.get("success"):
        print(f"\n🎉 收集成功！")
        print(f"   收集文件: {result['files_collected']}")
        print(f"   报告位置: {result['report_path']}")
        sys.exit(0)
    else:
        print(f"\n❌ 收集失败: {result.get('error')}")
        sys.exit(1)
