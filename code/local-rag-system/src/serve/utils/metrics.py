import time
import threading
from typing import Dict, Any, List
from collections import defaultdict, deque
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

from ...config import config

logger = logging.getLogger(__name__)

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # 请求指标
        self.request_counts = defaultdict(int)  # {endpoint: count}
        self.request_latencies = defaultdict(list)  # {endpoint: [latency]}
        self.status_codes = defaultdict(lambda: defaultdict(int))  # {endpoint: {status_code: count}}
        
        # 搜索相关指标
        self.search_queries = deque(maxlen=10000)  # 最近查询
        self.search_results_counts = deque(maxlen=10000)  # 结果数量
        self.search_latencies = deque(maxlen=1000)  # 搜索延迟
        
        # 问答相关指标
        self.ask_queries = deque(maxlen=1000)  # 最近问答
        self.groundedness_scores = deque(maxlen=1000)  # 基础性分数
        self.llm_latencies = deque(maxlen=1000)  # LLM延迟
        
        # 系统指标
        self.start_time = time.time()
        self.error_count = 0
        
        # 配置
        self.metrics_retention = config.get('monitoring', {}).get('metrics_retention_days', 30)
        self.metrics_file = Path(config.settings.data_base_dir) / "metrics.json"
    
    def record_request(self, method: str, path: str, status_code: int, 
                      process_time: float):
        """记录请求指标"""
        try:
            with self.lock:
                endpoint = f"{method} {path}"
                
                # 更新计数
                self.request_counts[endpoint] += 1
                
                # 记录延迟
                self.request_latencies[endpoint].append(process_time)
                
                # 限制延迟历史长度
                if len(self.request_latencies[endpoint]) > 1000:
                    self.request_latencies[endpoint] = self.request_latencies[endpoint][-1000:]
                
                # 记录状态码
                self.status_codes[endpoint][status_code] += 1
                
                # 记录错误
                if status_code >= 400:
                    self.error_count += 1
                
        except Exception as e:
            logger.error(f"Failed to record request metrics: {e}")
    
    def record_search(self, query: str, results_count: int, query_time_ms: float):
        """记录搜索指标"""
        try:
            with self.lock:
                self.search_queries.append({
                    "timestamp": time.time(),
                    "query": query,
                    "query_length": len(query)
                })
                
                self.search_results_counts.append({
                    "timestamp": time.time(),
                    "results_count": results_count
                })
                
                self.search_latencies.append(query_time_ms)
                
        except Exception as e:
            logger.error(f"Failed to record search metrics: {e}")
    
    def record_ask(self, query: str, groundedness_score: float, 
                   llm_time_ms: float, total_time_ms: float):
        """记录问答指标"""
        try:
            with self.lock:
                self.ask_queries.append({
                    "timestamp": time.time(),
                    "query": query,
                    "query_length": len(query)
                })
                
                self.groundedness_scores.append(groundedness_score)
                self.llm_latencies.append(llm_time_ms)
                
        except Exception as e:
            logger.error(f"Failed to record ask metrics: {e}")
    
    def get_request_metrics(self) -> Dict[str, Any]:
        """获取请求指标"""
        try:
            with self.lock:
                total_requests = sum(self.request_counts.values())
                total_errors = self.error_count
                error_rate = total_errors / total_requests if total_requests > 0 else 0
                
                # 计算延迟统计
                all_latencies = []
                for latencies in self.request_latencies.values():
                    all_latencies.extend(latencies)
                
                latency_stats = {}
                if all_latencies:
                    latency_stats = {
                        "p50": sorted(all_latencies)[len(all_latencies)//2],
                        "p95": sorted(all_latencies)[int(len(all_latencies)*0.95)],
                        "p99": sorted(all_latencies)[int(len(all_latencies)*0.99)],
                        "avg": sum(all_latencies) / len(all_latencies),
                        "min": min(all_latencies),
                        "max": max(all_latencies)
                    }
                
                # 热门端点
                popular_endpoints = sorted(
                    self.request_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
                
                return {
                    "total_requests": total_requests,
                    "total_errors": total_errors,
                    "error_rate": error_rate,
                    "latency_stats": latency_stats,
                    "popular_endpoints": dict(popular_endpoints),
                    "status_code_distribution": dict(self.status_codes)
                }
                
        except Exception as e:
            logger.error(f"Failed to get request metrics: {e}")
            return {}
    
    def get_search_metrics(self) -> Dict[str, Any]:
        """获取搜索指标"""
        try:
            with self.lock:
                if not self.search_results_counts:
                    return {
                        "total_searches": 0,
                        "average_results": 0,
                        "average_latency_ms": 0,
                        "hit_rate": 0
                    }
                
                # 搜索数量
                total_searches = len(self.search_results_counts)
                
                # 结果数量统计
                results_counts = [item["results_count"] for item in self.search_results_counts]
                avg_results = sum(results_counts) / len(results_counts)
                
                # 延迟统计
                if self.search_latencies:
                    avg_latency = sum(self.search_latencies) / len(self.search_latencies)
                    p95_latency = sorted(self.search_latencies)[int(len(self.search_latencies)*0.95)]
                else:
                    avg_latency = 0
                    p95_latency = 0
                
                # 命中率（结果数量 > 0的比例）
                hit_count = sum(1 for count in results_counts if count > 0)
                hit_rate = hit_count / len(results_counts)
                
                return {
                    "total_searches": total_searches,
                    "average_results": avg_results,
                    "average_latency_ms": avg_latency,
                    "p95_latency_ms": p95_latency,
                    "hit_rate": hit_rate,
                    "empty_search_rate": 1 - hit_rate
                }
                
        except Exception as e:
            logger.error(f"Failed to get search metrics: {e}")
            return {}
    
    def get_ask_metrics(self) -> Dict[str, Any]:
        """获取问答指标"""
        try:
            with self.lock:
                if not self.groundedness_scores:
                    return {
                        "total_asks": 0,
                        "average_groundedness": 0,
                        "average_llm_latency_ms": 0
                    }
                
                total_asks = len(self.groundedness_scores)
                
                # 基础性分数
                avg_groundedness = sum(self.groundedness_scores) / len(self.groundedness_scores)
                
                # LLM延迟
                if self.llm_latencies:
                    avg_llm_latency = sum(self.llm_latencies) / len(self.llm_latencies)
                    p95_llm_latency = sorted(self.llm_latencies)[int(len(self.llm_latencies)*0.95)]
                else:
                    avg_llm_latency = 0
                    p95_llm_latency = 0
                
                return {
                    "total_asks": total_asks,
                    "average_groundedness": avg_groundedness,
                    "average_llm_latency_ms": avg_llm_latency,
                    "p95_llm_latency_ms": p95_llm_latency
                }
                
        except Exception as e:
            logger.error(f"Failed to get ask metrics: {e}")
            return {}
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        try:
            uptime = time.time() - self.start_time
            
            return {
                "uptime_seconds": uptime,
                "uptime_days": uptime / 86400,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "current_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {}
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "request_metrics": self.get_request_metrics(),
            "search_metrics": self.get_search_metrics(),
            "ask_metrics": self.get_ask_metrics(),
            "system_metrics": self.get_system_metrics(),
            "collection_timestamp": datetime.now().isoformat()
        }
    
    def save_metrics(self):
        """保存指标到文件"""
        try:
            with self.lock:
                metrics = self.get_all_metrics()
                
                # 确保目录存在
                self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 保存到文件
                with open(self.metrics_file, 'w', encoding='utf-8') as f:
                    json.dump(metrics, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Metrics saved to {self.metrics_file}")
                
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def load_metrics(self) -> Dict[str, Any]:
        """从文件加载指标"""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    metrics = json.load(f)
                return metrics
            return {}
            
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
            return {}
    
    def reset_metrics(self):
        """重置指标"""
        try:
            with self.lock:
                self.request_counts.clear()
                self.request_latencies.clear()
                self.status_codes.clear()
                
                self.search_queries.clear()
                self.search_results_counts.clear()
                self.search_latencies.clear()
                
                self.ask_queries.clear()
                self.groundedness_scores.clear()
                self.llm_latencies.clear()
                
                self.error_count = 0
                self.start_time = time.time()
                
                logger.info("Metrics reset successfully")
                
        except Exception as e:
            logger.error(f"Failed to reset metrics: {e}")
    
    def cleanup_old_metrics(self):
        """清理过期指标"""
        try:
            with self.lock:
                current_time = time.time()
                cutoff_time = current_time - (self.metrics_retention * 24 * 3600)
                
                # 清理搜索查询
                self.search_queries = deque(
                    (item for item in self.search_queries if item["timestamp"] > cutoff_time),
                    maxlen=10000
                )
                
                # 清理搜索结果
                self.search_results_counts = deque(
                    (item for item in self.search_results_counts if item["timestamp"] > cutoff_time),
                    maxlen=10000
                )
                
                # 清理问答记录
                self.ask_queries = deque(
                    (item for item in self.ask_queries if item["timestamp"] > cutoff_time),
                    maxlen=1000
                )
                
                logger.info("Old metrics cleaned up successfully")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")

# 全局指标收集器实例
metrics_collector = MetricsCollector()