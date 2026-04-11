from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Dict, Any, Optional
import logging
import time
import uuid

from ...models import SearchRequest, AskRequest, SearchResponse, AskResponse
from ...search.hybrid_searcher import hybrid_searcher
from ...search.reranker import reranker
from ...ingest.processor import DocumentProcessor
from ...response_generator import ResponseGenerator
from ...session_manager import SessionManager
from ...middleware.auth import get_current_user, get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter()

# 创建会话管理器
session_manager = SessionManager()

@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """搜索文档"""
    start_time = time.time()
    
    try:
        # 记录用户查询
        session_id = request.session_id or str(uuid.uuid4())
        session_manager.log_query(session_id, request.query, current_user)
        
        # 参数验证
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if request.top_k < 1 or request.top_k > 100:
            raise HTTPException(status_code=400, detail="top_k must be between 1 and 100")
        
        # 执行混合搜索
        search_results = hybrid_searcher.search_with_fallback(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters.dict() if request.filters else None
        )
        
        # 重排序（如果启用）
        if request.rerank_enabled and len(search_results) > 1:
            search_results = reranker.rerank_with_fallback(
                query=request.query,
                documents=search_results,
                top_n=request.top_k
            )
        
        # 转换为标准格式
        formatted_results = []
        for result in search_results:
            formatted_result = {
                "doc_id": result.get("doc_id", ""),
                "chunk_id": result.get("chunk_id", ""),
                "content": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "scores": {
                    "hybrid_score": result.get("hybrid_score", 0.0),
                    "vector_score": result.get("vector_score", 0.0),
                    "bm25_score": result.get("bm25_score", 0.0),
                    "rerank_score": result.get("rerank_score")
                },
                "snippet": _generate_snippet(result.get("content", ""), request.query)
            }
            formatted_results.append(formatted_result)
        
        query_time = (time.time() - start_time) * 1000  # 转换为毫秒
        
        # 记录搜索结果
        background_tasks.add_task(
            session_manager.log_search_results,
            session_id,
            formatted_results,
            query_time
        )
        
        response = SearchResponse(
            results=formatted_results,
            query_time_ms=query_time,
            total_results=len(formatted_results),
            has_fallback=any("fallback_method" in result for result in search_results),
            search_metadata={
                "session_id": session_id,
                "rerank_enabled": request.rerank_enabled,
                "filters_applied": request.filters is not None
            }
        )
        
        logger.info(f"Search completed: {len(formatted_results)} results in {query_time:.2f}ms")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during search")

@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """问答接口"""
    start_time = time.time()
    
    try:
        # 记录用户查询
        session_id = request.session_id or str(uuid.uuid4())
        session_manager.log_query(session_id, request.query, current_user)
        
        # 参数验证
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        if request.top_k < 1 or request.top_k > 20:
            raise HTTPException(status_code=400, detail="top_k must be between 1 and 20")
        
        # 执行混合搜索获取相关文档
        search_start = time.time()
        search_results = hybrid_searcher.search_with_fallback(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters.dict() if request.filters else None
        )
        
        # 重排序（如果启用）
        if request.rerank_enabled and len(search_results) > 1:
            search_results = reranker.rerank_with_fallback(
                query=request.query,
                documents=search_results,
                top_n=request.top_k
            )
        
        search_time = (time.time() - search_start) * 1000
        
        # 准备搜索结果
        formatted_results = []
        for result in search_results:
            formatted_result = {
                "doc_id": result.get("doc_id", ""),
                "chunk_id": result.get("chunk_id", ""),
                "content": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "scores": {
                    "hybrid_score": result.get("hybrid_score", 0.0),
                    "vector_score": result.get("vector_score", 0.0),
                    "bm25_score": result.get("bm25_score", 0.0),
                    "rerank_score": result.get("rerank_score")
                }
            }
            formatted_results.append(formatted_result)
        
        # 如果没有搜索结果，返回空回答
        if not formatted_results:
            response = AskResponse(
                answer="抱歉，我没有找到与您的问题相关的信息。请尝试用不同的方式描述您的问题。",
                sources=[],
                query_time_ms=search_time,
                llm_time_ms=0,
                session_id=session_id,
                groundedness_score=0.0
            )
            return response
        
        # 生成回答
        llm_start = time.time()
        response_generator = ResponseGenerator()
        
        answer, groundedness_score = response_generator.generate_answer(
            question=request.query,
            context_docs=formatted_results
        )
        
        llm_time = (time.time() - llm_start) * 1000
        total_time = (time.time() - start_time) * 1000
        
        # 记录问答结果
        background_tasks.add_task(
            session_manager.log_ask_results,
            session_id,
            answer,
            groundedness_score,
            total_time
        )
        
        response = AskResponse(
            answer=answer,
            sources=formatted_results,
            query_time_ms=search_time,
            llm_time_ms=llm_time,
            session_id=session_id,
            groundedness_score=groundedness_score
        )
        
        logger.info(f"Ask completed: {len(formatted_results)} sources, answer length: {len(answer)} chars, total_time: {total_time:.2f}ms")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ask error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during ask")

@router.get("/similar/{chunk_id}")
async def find_similar_documents(
    chunk_id: str,
    top_k: int = 10,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """查找相似文档"""
    try:
        if top_k < 1 or top_k > 50:
            raise HTTPException(status_code=400, detail="top_k must be between 1 and 50")
        
        # 获取原始文档
        original_doc = hybrid_searcher.get_document_by_id(chunk_id)
        if not original_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # 使用原始文档内容查询相似文档
        similar_docs = hybrid_searcher.search_with_fallback(
            query=original_doc.content,
            top_k=top_k + 1  # +1 因为会包含自己
        )
        
        # 过滤掉自己
        similar_docs = [doc for doc in similar_docs if doc.get("chunk_id") != chunk_id]
        
        # 格式化结果
        formatted_results = []
        for result in similar_docs[:top_k]:
            formatted_result = {
                "doc_id": result.get("doc_id", ""),
                "chunk_id": result.get("chunk_id", ""),
                "content": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "scores": result.get("scores", {})
            }
            formatted_results.append(formatted_result)
        
        return {
            "original_chunk_id": chunk_id,
            "similar_documents": formatted_results,
            "total_results": len(formatted_results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Similar documents error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/suggestions")
async def get_search_suggestions(
    q: str = "",
    limit: int = 10,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """获取搜索建议"""
    try:
        if not q or len(q.strip()) < 2:
            return {"suggestions": []}
        
        if limit < 1 or limit > 20:
            limit = 10
        
        # 从元数据存储中搜索匹配的文档
        suggestions = []
        
        # 简单的实现：搜索文档标题和内容
        from ...store.metadata_store import metadata_store
        
        search_docs = metadata_store.search_documents(
            query=q.strip(),
            limit=limit,
            filters={"min_token_count": 10}
        )
        
        seen_suggestions = set()
        for doc in search_docs:
            # 提取可能的建议（如标题、关键词等）
            content_preview = doc.content[:100] + "..." if len(doc.content) > 100 else doc.content
            
            # 避免重复建议
            suggestion_key = content_preview[:50]
            if suggestion_key not in seen_suggestions:
                suggestions.append({
                    "text": content_preview,
                    "doc_id": doc.chunk_id,
                    "type": "content_preview"
                })
                seen_suggestions.add(suggestion_key)
            
            if len(suggestions) >= limit:
                break
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Search suggestions error: {e}")
        return {"suggestions": []}

@router.get("/history/{session_id}")
async def get_search_history(
    session_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """获取搜索历史"""
    try:
        history = session_manager.get_session_history(session_id)
        return {
            "session_id": session_id,
            "history": history
        }
        
    except Exception as e:
        logger.error(f"Search history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get search history")

def _generate_snippet(content: str, query: str, max_length: int = 200) -> str:
    """生成搜索结果摘要"""
    if not content:
        return ""
    
    # 简单的摘要生成：查找查询词在内容中的位置，并提取周围文本
    content_lower = content.lower()
    query_lower = query.lower()
    
    # 查找第一个匹配位置
    match_pos = content_lower.find(query_lower)
    
    if match_pos == -1:
        # 没有找到匹配词，返回开头部分
        return content[:max_length] + "..." if len(content) > max_length else content
    
    # 计算摘要的起始和结束位置
    snippet_start = max(0, match_pos - 50)
    snippet_end = min(len(content), match_pos + len(query) + 100)
    
    snippet = content[snippet_start:snippet_end]
    
    # 添加省略号
    if snippet_start > 0:
        snippet = "..." + snippet
    if snippet_end < len(content):
        snippet = snippet + "..."
    
    return snippet