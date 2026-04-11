from typing import List, Dict, Any, Optional, Tuple
import logging
import re
from datetime import datetime

from ..models import DocumentChunkWithMetadata
from ..config import config

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """响应生成器"""
    
    def __init__(self):
        self.config = config.get('llm', {})
        self.max_tokens = self.config.get('max_tokens', 2000)
        self.temperature = self.config.get('temperature', 0.1)
        self.system_prompt = self._get_system_prompt()
    
    def generate_answer(self, question: str, context_docs: List[Dict[str, Any]]) -> Tuple[str, float]:
        """生成回答"""
        try:
            if not context_docs:
                return "抱歉，我没有找到相关的信息来回答您的问题。", 0.0
            
            # 构建上下文
            context = self._build_context(context_docs)
            
            # 构建用户提示
            user_prompt = self._build_user_prompt(question, context)
            
            # 调用LLM生成回答
            answer = self._call_llm(self.system_prompt, user_prompt)
            
            # 计算基础性分数
            groundedness_score = self._calculate_groundedness(answer, context_docs)
            
            logger.info(f"Generated answer with groundedness score: {groundedness_score:.3f}")
            return answer, groundedness_score
            
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            return "抱歉，我在生成回答时遇到了问题，请稍后重试。", 0.0
    
    def _build_context(self, context_docs: List[Dict[str, Any]]) -> str:
        """构建上下文信息"""
        context_parts = []
        
        for i, doc in enumerate(context_docs, 1):
            # 提取文档信息
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            # 构建文档引用
            doc_ref = f"[文档{i}]"
            
            # 添加文件路径信息
            file_path = metadata.get('file_path', '')
            if file_path:
                filename = file_path.split('/')[-1]
                doc_ref += f"({filename})"
            
            # 添加位置信息
            if 'sheet_name' in metadata:
                doc_ref += f"[表格:{metadata['sheet_name']}]"
            elif 'slide_number' in metadata:
                doc_ref += f"[幻灯片:{metadata['slide_number']}]"
            elif 'line_start' in metadata:
                doc_ref += f"[行:{metadata['line_start']}-{metadata.get('line_end', '')}]"
            
            # 构建上下文段落
            context_text = f"{doc_ref}\n{content}"
            context_parts.append(context_text)
        
        return "\n\n".join(context_parts)
    
    def _build_user_prompt(self, question: str, context: str) -> str:
        """构建用户提示"""
        prompt = f"""请根据以下上下文信息回答用户的问题。

上下文信息：
{context}

用户问题：{question}

请遵循以下要求：
1. 基于提供的上下文信息进行回答
2. 如果上下文中没有相关信息，请明确说明
3. 回答要准确、简洁、有用
4. 在回答中引用相关的文档编号，格式如[文档1]、[文档2]等
5. 如果有具体的数值、日期、地点等信息，请精确引用

回答："""
        
        return prompt
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用LLM生成回答"""
        try:
            # 这里暂时使用模拟实现，实际应该调用Claude API
            return self._mock_llm_response(system_prompt, user_prompt)
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    def _mock_llm_response(self, system_prompt: str, user_prompt: str) -> str:
        """模拟LLM响应（用于开发测试）"""
        # 这里可以返回一个基于上下文的简单回答
        # 实际部署时需要替换为真正的Claude API调用
        
        # 简单的基于关键词的回答生成
        question_lower = user_prompt.lower()
        
        if "销售额" in question_lower or "销售" in question_lower:
            return """根据上下文信息[文档1]，2024年第一季度的销售数据显示：
- 产品A销售额为10,000元
- 产品B销售额为15,000元  
- 产品C销售额为8,000元

总体来看，第一季度总销售额为33,000元，其中产品B表现最佳[文档1]。"""
        
        elif "函数" in question_lower or "代码" in question_lower:
            return """根据上下文信息[文档1]，代码中定义了以下函数：

1. calculate_sum函数：用于计算两个数的和[文档1]
   - 参数：a, b (整数类型)
   - 返回值：两个数的和

2. Calculator类：简单计算器类[文档1]
   - 包含add方法用于加法运算
   - 维护历史记录功能[文档1]

这些函数都包含了完整的文档字符串和类型注解[文档1]。"""
        
        elif "幻灯片" in question_lower or "ppt" in question_lower:
            return """根据提供的演示文稿信息[文档1]：

该演示文稿包含多个幻灯片，每个幻灯片都有标题和内容[文档1]。部分幻灯片还包含备注信息，可用于演讲时的参考[文档1]。

建议按照幻灯片的顺序进行演示，并利用备注内容来增强演讲效果[文档1]。"""
        
        else:
            return """根据提供的上下文信息，我找到了相关的文档内容[文档1]。这些文档包含了与您问题相关的详细信息。

建议您参考[文档1]中的具体信息来了解更多细节。如果您需要更具体的解释或有其他问题，请随时提出。"""
    
    def _calculate_groundedness(self, answer: str, context_docs: List[Dict[str, Any]]) -> float:
        """计算回答的基础性分数"""
        if not answer or not context_docs:
            return 0.0
        
        # 提取上下文中的关键词
        context_keywords = set()
        for doc in context_docs:
            content = doc.get('content', '').lower()
            # 简单的关键词提取
            words = re.findall(r'\b\w+\b', content)
            for word in words:
                if len(word) >= 3:  # 只考虑长度>=3的词
                    context_keywords.add(word)
        
        # 计算回答中与上下文匹配的词
        answer_words = re.findall(r'\b\w+\b', answer.lower())
        matched_words = [word for word in answer_words if word in context_keywords]
        
        # 计算基础性分数
        if len(answer_words) == 0:
            return 0.0
        
        groundedness = len(matched_words) / len(answer_words)
        
        # 检查引用完整性
        citations = re.findall(r'\[文档\d+\]', answer)
        if context_docs and not citations:
            groundedness *= 0.8  # 有上下文但没有引用，降低分数
        
        return min(1.0, groundedness)
    
    def _get_system_prompt(self) -> str:
        """获取系统提示"""
        return """你是一个专业的文档分析和问答助手。你的任务是基于提供的上下文信息回答用户的问题。

重要原则：
1. 只能基于提供的上下文信息进行回答
2. 如果上下文信息不足，要明确说明
3. 回答要准确、客观、简洁
4. 在适当的地方引用具体的文档编号
5. 保持专业和友好的语调

注意事项：
- 不要编造上下文中没有的信息
- 如果对某个信息不确定，要说明
- 优先回答用户的具体问题
- 保持回答的逻辑性和连贯性"""
    
    def extract_citations(self, answer: str) -> List[str]:
        """提取回答中的引用"""
        return re.findall(r'\[文档\d+\]', answer)
    
    def validate_answer(self, answer: str, context_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证回答质量"""
        validation_result = {
            "is_valid": True,
            "issues": [],
            "citations": [],
            "groundedness_score": 0.0
        }
        
        # 检查回答是否为空
        if not answer or not answer.strip():
            validation_result["is_valid"] = False
            validation_result["issues"].append("回答为空")
            return validation_result
        
        # 提取引用
        citations = self.extract_citations(answer)
        validation_result["citations"] = citations
        
        # 计算基础性分数
        groundedness = self._calculate_groundedness(answer, context_docs)
        validation_result["groundedness_score"] = groundedness
        
        # 检查基础性问题
        if groundedness < 0.3:
            validation_result["issues"].append("回答与上下文相关性较低")
        
        if len(citations) == 0 and context_docs:
            validation_result["issues"].append("缺少文档引用")
        
        # 检查长度
        if len(answer) > self.max_tokens * 2:  # 简单的长度检查
            validation_result["issues"].append("回答过长")
        
        return validation_result
    
    def update_config(self, **kwargs):
        """更新配置"""
        if 'max_tokens' in kwargs:
            self.max_tokens = kwargs['max_tokens']
        if 'temperature' in kwargs:
            self.temperature = kwargs['temperature']
        if 'system_prompt' in kwargs:
            self.system_prompt = kwargs['system_prompt']
        
        logger.info(f"Updated response generator config: {kwargs}")
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system_prompt_length": len(self.system_prompt)
        }