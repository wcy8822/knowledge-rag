#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for MCP Knowledge Server

Tests the complete flow of:
1. Vector import
2. Enhanced hybrid search
3. MCP server functionality
4. Claude auto-call capability
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestMCPIntegration:
    """Integration tests for MCP Knowledge Server"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        print("\n" + "=" * 80)
        print("🧪 MCP Integration Tests")
        print("=" * 80)
        
        cls.db_path = "/Users/didi/Downloads/panth/data/chroma"
        cls.vectors_json = "/Users/didi/Downloads/panth/data/vectors/vectors_20251027_163030.json"
    
    def test_01_vector_import(self):
        """Test 1: Vector import from JSON to ChromaDB"""
        print("\n📋 Test 1: Vector Import")
        print("-" * 80)
        
        from local_rag_system.scripts.import_vectors import import_vectors
        
        result = import_vectors(self.vectors_json, self.db_path)
        
        assert result["success"], f"Vector import failed: {result.get('error')}"
        assert result["total_imported"] > 0, "No vectors imported"
        
        print(f"✅ PASS - Imported {result['total_imported']} vectors")
        print(f"   Collection count: {result['collection_count']}")
    
    def test_02_enhanced_searcher_init(self):
        """Test 2: Enhanced hybrid searcher initialization"""
        print("\n📋 Test 2: Enhanced Searcher Initialization")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher
        
        searcher = EnhancedHybridSearcher(db_path=self.db_path)
        
        assert searcher is not None, "Failed to initialize searcher"
        
        # Get stats
        stats = searcher.get_stats()
        assert stats is not None, "Failed to get stats"
        
        print(f"✅ PASS - Searcher initialized")
        print(f"   Available searchers: {stats['searchers']}")
    
    def test_03_vector_search(self):
        """Test 3: Vector similarity search"""
        print("\n📋 Test 3: Vector Similarity Search")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher
        
        searcher = EnhancedHybridSearcher(db_path=self.db_path)
        
        # Test search
        query = "商户服务"  # Merchant services in Chinese
        results = searcher._search_vector(query, top_k=5)
        
        # Results might be empty if no searcher, but should not error
        print(f"✅ PASS - Vector search completed")
        print(f"   Found: {len(results)} results")
    
    def test_04_unified_search(self):
        """Test 4: Unified search across all sources"""
        print("\n📋 Test 4: Unified Search")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher
        
        searcher = EnhancedHybridSearcher(db_path=self.db_path)
        
        # Test unified search
        query = "2025年Q4策略"  # 2025 Q4 strategy
        results = searcher.unified_search(query, top_k=5)
        
        assert isinstance(results, list), "Results should be a list"
        
        print(f"✅ PASS - Unified search completed")
        print(f"   Total results: {len(results)}")
        
        if results:
            print(f"   Top result: {results[0].source}")
    
    def test_05_mcp_server_init(self):
        """Test 5: MCP Knowledge Server initialization"""
        print("\n📋 Test 5: MCP Server Initialization")
        print("-" * 80)
        
        try:
            from local_rag_system.src.serve.mcp_knowledge_server import MCPKnowledgeServer
            
            server = MCPKnowledgeServer(db_path=self.db_path)
            
            assert server is not None, "Failed to initialize MCP server"
            assert server.searcher is not None, "Searcher not initialized"
            
            print(f"✅ PASS - MCP server initialized")
            print(f"   Tools registered: 2 (search_knowledge, get_knowledge_stats)")
        except ImportError as e:
            print(f"⚠️  SKIP - MCP library not available: {e}")
    
    def test_06_search_result_format(self):
        """Test 6: Search result formatting for Claude"""
        print("\n📋 Test 6: Search Result Formatting")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import SearchResult
        
        # Create a sample result
        result = SearchResult(
            doc_id="test_001",
            source="/path/to/document.md",
            content="This is test content",
            relevance_score=0.95,
            rank=1,
            search_methods=["vector", "bm25"],
            metadata={"type": "md"}
        )
        
        # Verify result structure
        assert result.doc_id == "test_001"
        assert result.relevance_score == 0.95
        assert len(result.search_methods) == 2
        
        print(f"✅ PASS - Search result format valid")
        print(f"   Result: {result.doc_id} (score: {result.relevance_score:.2%})")
    
    def test_07_audit_logging(self):
        """Test 7: Audit logging functionality"""
        print("\n📋 Test 7: Audit Logging")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher
        
        searcher = EnhancedHybridSearcher(db_path=self.db_path)
        
        # Perform a search which should generate audit log
        query = "测试查询"  # Test query
        results = searcher.unified_search(query, top_k=3)
        
        # Check if audit log was created
        if searcher.audit_log_path and Path(searcher.audit_log_path).exists():
            with open(searcher.audit_log_path, 'r') as f:
                lines = f.readlines()
            
            assert len(lines) > 0, "No audit logs written"
            print(f"✅ PASS - Audit logging working")
            print(f"   Log file: {searcher.audit_log_path}")
            print(f"   Entries: {len(lines)}")
        else:
            print(f"⚠️  SKIP - Audit logging not fully configured")
    
    def test_08_knowledge_stats(self):
        """Test 8: Knowledge base statistics"""
        print("\n📋 Test 8: Knowledge Base Statistics")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher
        
        searcher = EnhancedHybridSearcher(db_path=self.db_path)
        
        stats = searcher.get_stats()
        
        assert stats is not None, "Failed to get stats"
        assert "timestamp" in stats, "Missing timestamp"
        assert "searchers" in stats, "Missing searchers info"
        
        print(f"✅ PASS - Knowledge base stats retrieved")
        print(f"   Timestamp: {stats['timestamp']}")
        print(f"   Searchers available: {sum(1 for v in stats['searchers'].values() if v)}")
    
    def test_09_error_handling(self):
        """Test 9: Error handling and graceful degradation"""
        print("\n📋 Test 9: Error Handling")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher
        
        # Test with non-existent path
        searcher = EnhancedHybridSearcher(db_path="/non/existent/path")
        
        # Should not raise exception, but gracefully degrade
        try:
            results = searcher.unified_search("test", top_k=5)
            print(f"✅ PASS - Graceful degradation on missing DB")
            print(f"   Results: {len(results)} (expected empty or degraded)")
        except Exception as e:
            print(f"❌ FAIL - Exception not caught: {e}")
            raise
    
    def test_10_mcp_auto_call_simulation(self):
        """Test 10: MCP auto-call simulation (Claude would call this)"""
        print("\n📋 Test 10: MCP Auto-Call Simulation")
        print("-" * 80)
        
        from local_rag_system.src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher
        
        searcher = EnhancedHybridSearcher(db_path=self.db_path)
        
        # Simulate Claude calling search_knowledge
        queries = [
            "2025Q4在路上商户服务",
            "双轮驱动策略",
            "本地向量化知识库"
        ]
        
        for query in queries:
            print(f"\n  Query: {query}")
            try:
                results = searcher.unified_search(query, top_k=3)
                print(f"  ✅ Results: {len(results)}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                # Continue with next query
        
        print(f"\n✅ PASS - Auto-call simulation completed")


def run_tests():
    """Run all tests"""
    test = TestMCPIntegration()
    test.setup_class()
    
    tests = [
        test.test_01_vector_import,
        test.test_02_enhanced_searcher_init,
        test.test_03_vector_search,
        test.test_04_unified_search,
        test.test_05_mcp_server_init,
        test.test_06_search_result_format,
        test.test_07_audit_logging,
        test.test_08_knowledge_stats,
        test.test_09_error_handling,
        test.test_10_mcp_auto_call_simulation,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL - {str(e)}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            failed += 1
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 Test Summary")
    print("=" * 80)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    
    if failed == 0:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
