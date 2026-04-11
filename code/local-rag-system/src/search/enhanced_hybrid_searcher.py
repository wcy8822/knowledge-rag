#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Hybrid Searcher - Unified Knowledge Source Integration

Extends the existing HybridSearcher to integrate:
1. Vector search (from LocalRAG)
2. BM25 keyword search (from LocalRAG)
3. Chronicle semantic retrieval (from DPG)
4. Result fusion with reranking
5. Audit logging for quality monitoring
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Unified search result structure"""
    doc_id: str
    source: str
    content: str
    relevance_score: float
    rank: int
    search_methods: List[str]  # Which methods found this result
    metadata: Dict[str, Any]


class EnhancedHybridSearcher:
    """
    Enhanced hybrid searcher integrating multiple knowledge sources
    
    This class extends the existing hybrid search functionality to include:
    - Vector similarity search
    - BM25 keyword search  
    - Chronicle-based semantic retrieval
    - Intelligent result fusion
    """
    
    def __init__(self, db_path: str = None, chronicle_db_path: str = None):
        """
        Initialize the enhanced hybrid searcher
        
        Args:
            db_path: Path to ChromaDB database
            chronicle_db_path: Path to Chronicle database
        """
        self.db_path = db_path or "/Users/didi/Downloads/panth/data/chroma"
        self.chronicle_db_path = chronicle_db_path or "/Users/didi/Downloads/panth/dpg_system"
        
        # Import and initialize existing LocalRAG components
        try:
            from .vector_searcher import VectorSearcher
            self.vector_searcher = VectorSearcher(db_path=self.db_path)
            logger.info("✅ Vector searcher initialized")
        except Exception as e:
            logger.warning(f"⚠️ Vector searcher initialization failed: {e}")
            self.vector_searcher = None
        
        try:
            from .bm25_searcher import BM25Searcher
            self.bm25_searcher = BM25Searcher(db_path=self.db_path)
            logger.info("✅ BM25 searcher initialized")
        except Exception as e:
            logger.warning(f"⚠️ BM25 searcher initialization failed: {e}")
            self.bm25_searcher = None
        
        try:
            from .reranker import Reranker
            self.reranker = Reranker()
            logger.info("✅ Reranker initialized")
        except Exception as e:
            logger.warning(f"⚠️ Reranker initialization failed: {e}")
            self.reranker = None
        
        # Try to initialize Chronicle retriever from DPG system
        self.chronicle_retriever = self._init_chronicle()
        
        # Initialize audit logger
        self.audit_log = []
        self._init_audit()
    
    def _init_chronicle(self):
        """Initialize Chronicle retriever from DPG system"""
        try:
            import sys
            dpg_path = Path(self.chronicle_db_path).parent
            if str(dpg_path) not in sys.path:
                sys.path.insert(0, str(dpg_path))
            
            from dpg_system.src.data.chronicle_retriever import ChronicleRetriever
            chronicle = ChronicleRetriever()
            logger.info("✅ Chronicle retriever initialized")
            return chronicle
        except Exception as e:
            logger.warning(f"⚠️ Chronicle retriever initialization failed: {e}")
            return None
    
    def _init_audit(self):
        """Initialize audit logging"""
        try:
            logs_dir = Path("/Users/didi/Downloads/panth/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            self.audit_log_path = logs_dir / f"search_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            logger.info(f"✅ Audit logging initialized: {self.audit_log_path}")
        except Exception as e:
            logger.warning(f"⚠️ Audit logging initialization failed: {e}")
            self.audit_log_path = None
    
    def unified_search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Perform unified search across all knowledge sources
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of SearchResult objects ranked by relevance
        """
        search_start = datetime.now()
        logger.info(f"🔍 Starting unified search: {query}")
        
        # Collect results from all sources
        all_results = {}  # dict[doc_id] = SearchResult
        
        # 1. Vector search
        vector_results = self._search_vector(query, top_k * 2)
        for result in vector_results:
            all_results[result.doc_id] = result
        
        # 2. BM25 search
        bm25_results = self._search_bm25(query, top_k * 2)
        for result in bm25_results:
            if result.doc_id in all_results:
                # Merge: combine search methods
                all_results[result.doc_id].search_methods.extend(result.search_methods)
                # Average scores
                all_results[result.doc_id].relevance_score = (
                    all_results[result.doc_id].relevance_score + result.relevance_score
                ) / 2
            else:
                all_results[result.doc_id] = result
        
        # 3. Chronicle search
        chronicle_results = self._search_chronicle(query, top_k * 2)
        for result in chronicle_results:
            if result.doc_id in all_results:
                # Merge
                all_results[result.doc_id].search_methods.extend(result.search_methods)
                # Boost score if found in multiple sources
                all_results[result.doc_id].relevance_score *= 1.1  # 10% boost
            else:
                all_results[result.doc_id] = result
        
        # 4. Rerank results
        ranked_results = self._rerank_results(list(all_results.values()), query, top_k)
        
        # 5. Log audit
        search_duration = (datetime.now() - search_start).total_seconds()
        self._log_audit({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "top_k": top_k,
            "results_found": len(ranked_results),
            "all_results_found": len(all_results),
            "duration_seconds": search_duration,
            "search_methods": {
                "vector": len(vector_results) if vector_results else 0,
                "bm25": len(bm25_results) if bm25_results else 0,
                "chronicle": len(chronicle_results) if chronicle_results else 0
            },
            "success": True
        })
        
        logger.info(f"✅ Unified search completed: {len(ranked_results)} results in {search_duration:.2f}s")
        
        return ranked_results
    
    def _search_vector(self, query: str, top_k: int) -> List[SearchResult]:
        """Vector similarity search"""
        if not self.vector_searcher:
            return []
        
        try:
            results = self.vector_searcher.search(query, top_k=top_k)
            return [
                SearchResult(
                    doc_id=r.get("doc_id", f"vector_{i}"),
                    source=r.get("source", "unknown"),
                    content=r.get("content", ""),
                    relevance_score=r.get("score", 0.0),
                    rank=i,
                    search_methods=["vector"],
                    metadata=r.get("metadata", {})
                )
                for i, r in enumerate(results)
            ]
        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            return []
    
    def _search_bm25(self, query: str, top_k: int) -> List[SearchResult]:
        """BM25 keyword search"""
        if not self.bm25_searcher:
            return []
        
        try:
            results = self.bm25_searcher.search(query, top_k=top_k)
            return [
                SearchResult(
                    doc_id=r.get("doc_id", f"bm25_{i}"),
                    source=r.get("source", "unknown"),
                    content=r.get("content", ""),
                    relevance_score=r.get("score", 0.0),
                    rank=i,
                    search_methods=["bm25"],
                    metadata=r.get("metadata", {})
                )
                for i, r in enumerate(results)
            ]
        except Exception as e:
            logger.error(f"❌ BM25 search failed: {e}")
            return []
    
    def _search_chronicle(self, query: str, top_k: int) -> List[SearchResult]:
        """Chronicle semantic retrieval"""
        if not self.chronicle_retriever:
            return []
        
        try:
            results = self.chronicle_retriever.retrieve_with_vectors(query, top_k=top_k)
            return [
                SearchResult(
                    doc_id=r.get("doc_id", f"chronicle_{i}"),
                    source=r.get("source", "chronicle"),
                    content=r.get("content", ""),
                    relevance_score=r.get("score", 0.0),
                    rank=i,
                    search_methods=["chronicle"],
                    metadata=r.get("metadata", {})
                )
                for i, r in enumerate(results)
            ]
        except Exception as e:
            logger.warning(f"⚠️ Chronicle search not available: {e}")
            return []
    
    def _rerank_results(self, results: List[SearchResult], query: str, top_k: int) -> List[SearchResult]:
        """Rerank results using reranker"""
        if not self.reranker or not results:
            # Fallback: sort by relevance score
            results.sort(key=lambda r: r.relevance_score, reverse=True)
            for i, r in enumerate(results[:top_k]):
                r.rank = i + 1
            return results[:top_k]
        
        try:
            # Use reranker if available
            reranked = self.reranker.rerank(
                query=query,
                documents=[r.content for r in results],
                scores=[r.relevance_score for r in results]
            )
            
            # Update ranks and scores
            for i, (result, new_score) in enumerate(zip(results, reranked)):
                result.relevance_score = new_score
                result.rank = i + 1
            
            return results[:top_k]
        except Exception as e:
            logger.warning(f"⚠️ Reranking failed: {e}, falling back to score-based ranking")
            results.sort(key=lambda r: r.relevance_score, reverse=True)
            for i, r in enumerate(results[:top_k]):
                r.rank = i + 1
            return results[:top_k]
    
    def _log_audit(self, audit_entry: Dict[str, Any]):
        """Log search audit entry"""
        if not self.audit_log_path:
            return
        
        try:
            with open(self.audit_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"❌ Failed to log audit: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "searchers": {
                "vector": self.vector_searcher is not None,
                "bm25": self.bm25_searcher is not None,
                "chronicle": self.chronicle_retriever is not None,
                "reranker": self.reranker is not None
            }
        }
        
        # Get document counts
        if self.vector_searcher:
            try:
                stats["vector_db_docs"] = self.vector_searcher.get_doc_count()
            except:
                pass
        
        return stats
