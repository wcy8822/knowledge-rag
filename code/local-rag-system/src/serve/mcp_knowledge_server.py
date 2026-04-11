#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Knowledge Server - Claude Auto-Call Integration

This MCP server allows Claude to automatically call local knowledge base
functions without manual document supplementation.

The server exposes two main tools:
1. search_knowledge() - Search across all knowledge sources
2. get_knowledge_stats() - Get knowledge base statistics
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from mcp.server import FastMCP
    from mcp.types import TextContent
except ImportError:
    logger.error("❌ MCP library not found. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp"])
    from mcp.server import FastMCP
    from mcp.types import TextContent


class MCPKnowledgeServer:
    """MCP Server for Local Knowledge Base Access"""

    def __init__(self, db_path: str = None):
        """
        Initialize the MCP Knowledge Server

        Args:
            db_path: Path to ChromaDB database
        """
        self.db_path = db_path or "/Users/didi/Downloads/panth/data/chroma"

        # Create FastMCP server instance
        self.server = FastMCP("local-knowledge-base")

        # Initialize searcher
        self.searcher = self._init_searcher()

        # Register tools using FastMCP API
        self._register_tools()

        logger.info("✅ MCP Knowledge Server initialized")
    
    def _init_searcher(self):
        """Initialize the enhanced hybrid searcher"""
        try:
            # Try relative import first (when run as module)
            try:
                from ..search.enhanced_hybrid_searcher import EnhancedHybridSearcher
            except (ImportError, ValueError):
                # Fallback to absolute import (when run as script)
                from src.search.enhanced_hybrid_searcher import EnhancedHybridSearcher

            searcher = EnhancedHybridSearcher(db_path=self.db_path)
            logger.info("✅ Enhanced hybrid searcher initialized")
            return searcher
        except Exception as e:
            logger.error(f"❌ Failed to initialize searcher: {e}")
            logger.warning("⚠️ Falling back to minimal functionality (no search available)")
            # Return None - service can still run without searcher
            return None
    
    def _register_tools(self):
        """Register MCP tools using FastMCP API"""

        # Tool 1: Search Knowledge
        self.server.add_tool(
            self._handle_search_knowledge,
            name="search_knowledge",
            description="""Search the local knowledge base across all sources:
- Vector similarity search
- BM25 keyword search
- Chronicle semantic retrieval

Returns the most relevant documents matching the query.
Use this to find information from local files without manual supplementation."""
        )

        # Tool 2: Get Knowledge Base Stats
        self.server.add_tool(
            self._handle_get_knowledge_stats,
            name="get_knowledge_stats",
            description="""Get statistics about the local knowledge base:
- Total documents indexed
- Vector database size
- Available search methods
- Last update time

Use this to understand what knowledge is available and when it was last updated."""
        )

        logger.info("✅ Tools registered successfully")
    
    def _handle_search_knowledge(self, query: str, top_k: int = 5) -> str:
        """Handle search_knowledge tool call"""
        logger.info(f"🔍 Search request: {query} (top_k={top_k})")

        if not self.searcher:
            error_msg = "❌ Knowledge base not initialized. Please check logs."
            logger.error(error_msg)
            return error_msg

        try:
            # Perform search
            results = self.searcher.unified_search(query, top_k=top_k)

            if not results:
                msg = f"No results found for: {query}"
                logger.warning(msg)
                return msg

            # Format results for Claude
            formatted_results = self._format_search_results(results, query)

            logger.info(f"✅ Search completed: {len(results)} results found")

            return formatted_results

        except Exception as e:
            error_msg = f"❌ Search failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _handle_get_knowledge_stats(self) -> str:
        """Handle get_knowledge_stats tool call"""
        logger.info("📊 Stats request")

        try:
            if not self.searcher:
                stats = {
                    "status": "error",
                    "message": "Knowledge base not initialized"
                }
            else:
                stats = self.searcher.get_stats()
                stats["timestamp"] = datetime.now().isoformat()
                stats["db_path"] = self.db_path
                stats["status"] = "ready"

            stats_json = json.dumps(stats, ensure_ascii=False, indent=2)
            logger.info(f"✅ Stats retrieved: {stats.get('status', 'unknown')}")

            return stats_json

        except Exception as e:
            error_msg = f"❌ Failed to get stats: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _format_search_results(self, results: List[Any], query: str) -> str:
        """Format search results for Claude display"""
        
        output = f"""🔍 Knowledge Base Search Results
Query: "{query}"
Found: {len(results)} results

"""
        
        for i, result in enumerate(results, 1):
            # Get result attributes safely
            rank = getattr(result, 'rank', i)
            relevance = getattr(result, 'relevance_score', 0.0)
            source = getattr(result, 'source', 'unknown')
            content = getattr(result, 'content', '')[:200]  # First 200 chars
            search_methods = getattr(result, 'search_methods', [])
            
            output += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#{rank} (Relevance: {relevance:.2%})
📁 Source: {source}
🔎 Found by: {', '.join(search_methods)}

{content}{"..." if len(getattr(result, 'content', '')) > 200 else ""}

"""
        
        output += f"""
💡 To use this information:
- The content above is directly from your local knowledge base
- No network requests or external APIs were used
- All information is current as of the last vectorization

✅ Auto-call successful - no manual supplementation needed!
"""
        
        return output
    
    def run(self, stdio: bool = True):
        """
        Run the MCP server

        Args:
            stdio: If True, use stdio transport (for Claude integration)
        """
        logger.info("🚀 Starting MCP Knowledge Server")

        if stdio:
            logger.info("✅ MCP server running (stdio mode)")
            self.server.run(transport="stdio")
        else:
            # Alternative: run with other transports if needed
            logger.info("⚠️ Non-stdio mode not yet implemented")
            raise NotImplementedError("Only stdio transport is currently supported")


def main():
    """Main entry point for MCP server"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MCP Knowledge Server for Local Knowledge Base Access"
    )
    parser.add_argument(
        "--db-path",
        default="/Users/didi/Downloads/panth/data/chroma",
        help="Path to ChromaDB database"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("=" * 80)
    logger.info("🚀 MCP Knowledge Server Startup")
    logger.info("=" * 80)
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Log level: {args.log_level}")
    
    # Create and run server
    server = MCPKnowledgeServer(db_path=args.db_path)
    
    try:
        logger.info("Starting server with stdio transport...")
        server.run(stdio=True)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
