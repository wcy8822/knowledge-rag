from typing import Dict, Any, List, Optional
import logging
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
from pathlib import Path

from ..config import config

logger = logging.getLogger(__name__)

class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        self.config = config.get('session', {})
        self.max_sessions = self.config.get('max_sessions', 1000)
        self.session_timeout = self.config.get('session_timeout', 3600)  # 1小时
        self.max_history = self.config.get('max_history', 50)
        
        # 内存存储
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_queries: Dict[str, List[Dict[str, Any]]] = defaultdict(deque)
        self.user_sessions: Dict[str, set] = defaultdict(set)
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 定期清理过期会话
        self._cleanup_thread = None
        self._start_cleanup_task()
    
    def log_query(self, session_id: str, query: str, user: Optional[Dict[str, Any]] = None):
        """记录用户查询"""
        try:
            with self.lock:
                current_time = time.time()
                
                # 创建或更新会话
                if session_id not in self.sessions:
                    self.sessions[session_id] = {
                        "session_id": session_id,
                        "created_at": current_time,
                        "last_activity": current_time,
                        "user": user,
                        "query_count": 0,
                        "is_active": True
                    }
                    
                    # 关联用户和会话
                    if user and user.get("user_id"):
                        self.user_sessions[user["user_id"]].add(session_id)
                
                # 更新会话信息
                session = self.sessions[session_id]
                session["last_activity"] = current_time
                session["query_count"] += 1
                
                # 记录查询历史
                query_record = {
                    "timestamp": current_time,
                    "query": query,
                    "session_id": session_id
                }
                
                self.session_queries[session_id].append(query_record)
                
                # 限制历史记录长度
                if len(self.session_queries[session_id]) > self.max_history:
                    self.session_queries[session_id].popleft()
                
                logger.debug(f"Logged query for session {session_id}: {query[:50]}...")
                
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
    
    def log_search_results(self, session_id: str, results: List[Dict[str, Any]], 
                         query_time_ms: float):
        """记录搜索结果"""
        try:
            with self.lock:
                if session_id in self.session_queries and self.session_queries[session_id]:
                    # 更新最近的查询记录
                    latest_query = self.session_queries[session_id][-1]
                    latest_query["search_results"] = {
                        "count": len(results),
                        "query_time_ms": query_time_ms,
                        "has_results": len(results) > 0,
                        "top_result_score": results[0]["scores"].get("hybrid_score", 0.0) if results else 0.0
                    }
                
        except Exception as e:
            logger.error(f"Failed to log search results: {e}")
    
    def log_ask_results(self, session_id: str, answer: str, 
                      groundedness_score: float, total_time_ms: float):
        """记录问答结果"""
        try:
            with self.lock:
                if session_id in self.session_queries and self.session_queries[session_id]:
                    # 更新最近的查询记录
                    latest_query = self.session_queries[session_id][-1]
                    latest_query["ask_results"] = {
                        "answer_length": len(answer),
                        "groundedness_score": groundedness_score,
                        "total_time_ms": total_time_ms,
                        "has_answer": len(answer) > 0
                    }
                
        except Exception as e:
            logger.error(f"Failed to log ask results: {e}")
    
    def get_session_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取会话历史"""
        try:
            with self.lock:
                if session_id not in self.session_queries:
                    return []
                
                history = list(self.session_queries[session_id])
                history.reverse()  # 最新的在前
                
                return history[:limit]
                
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            with self.lock:
                return self.sessions.get(session_id)
                
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return None
    
    def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有会话"""
        try:
            with self.lock:
                if user_id not in self.user_sessions:
                    return []
                
                user_session_ids = self.user_sessions[user_id]
                user_sessions = []
                
                for session_id in user_session_ids:
                    if session_id in self.sessions:
                        user_sessions.append(self.sessions[session_id].copy())
                
                return user_sessions
                
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            with self.lock:
                if session_id not in self.sessions:
                    return False
                
                session = self.sessions[session_id]
                
                # 从用户会话映射中移除
                user = session.get("user")
                if user and user.get("user_id"):
                    self.user_sessions[user["user_id"]].discard(session_id)
                    if not self.user_sessions[user["user_id"]]:
                        del self.user_sessions[user["user_id"]]
                
                # 删除会话和查询历史
                del self.sessions[session_id]
                if session_id in self.session_queries:
                    del self.session_queries[session_id]
                
                logger.info(f"Deleted session: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """清理过期会话"""
        try:
            with self.lock:
                current_time = time.time()
                expired_sessions = []
                
                # 查找过期会话
                for session_id, session in self.sessions.items():
                    last_activity = session.get("last_activity", 0)
                    if current_time - last_activity > self.session_timeout:
                        expired_sessions.append(session_id)
                
                # 删除过期会话
                for session_id in expired_sessions:
                    self.delete_session(session_id)
                
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                
                return len(expired_sessions)
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            with self.lock:
                current_time = time.time()
                
                active_sessions = 0
                total_queries = 0
                session_durations = []
                
                for session in self.sessions.values():
                    last_activity = session.get("last_activity", 0)
                    created_at = session.get("created_at", 0)
                    
                    if current_time - last_activity <= self.session_timeout:
                        active_sessions += 1
                    
                    total_queries += session.get("query_count", 0)
                    session_durations.append(current_time - created_at)
                
                # 计算统计指标
                avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0
                
                return {
                    "total_sessions": len(self.sessions),
                    "active_sessions": active_sessions,
                    "total_queries": total_queries,
                    "average_queries_per_session": total_queries / len(self.sessions) if self.sessions else 0,
                    "average_session_duration_minutes": avg_session_duration / 60,
                    "total_users": len(self.user_sessions),
                    "memory_usage_estimate": {
                        "sessions_count": len(self.sessions),
                        "queries_in_memory": sum(len(queries) for queries in self.session_queries.values())
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {}
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(300)  # 每5分钟清理一次
                    self.cleanup_expired_sessions()
                except Exception as e:
                    logger.error(f"Cleanup task error: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("Session cleanup task started")
    
    def export_session_data(self, session_id: str, file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """导出会话数据"""
        try:
            with self.lock:
                if session_id not in self.sessions:
                    return None
                
                session_info = self.sessions[session_id].copy()
                session_history = list(self.session_queries[session_id])
                
                export_data = {
                    "session_info": session_info,
                    "history": session_history,
                    "export_timestamp": time.time()
                }
                
                # 如果指定了文件路径，保存到文件
                if file_path:
                    export_file = Path(file_path)
                    export_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(export_file, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"Session data exported to: {file_path}")
                
                return export_data
                
        except Exception as e:
            logger.error(f"Failed to export session data: {e}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            stats = self.get_session_statistics()
            
            return {
                "status": "healthy",
                "session_statistics": stats,
                "configuration": {
                    "max_sessions": self.max_sessions,
                    "session_timeout": self.session_timeout,
                    "max_history": self.max_history
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }