from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import ast
import re
import inspect

from .base_parser import BaseParser
from ...models.document import DocumentWithChunks, DocumentChunkWithMetadata, CodeMetadata, DataSource

class CodeParser(BaseParser):
    """代码文件解析器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.supported_languages = set(self.config.get('languages', [
            'python', 'javascript', 'java', 'cpp', 'c', 'go', 'rust'
        ]))
        self.extract_comments = self.config.get('extract_comments', True)
        self.extract_docstrings = self.config.get('extract_docstrings', True)
        self.max_function_length = self.config.get('max_function_length', 100)
        
        # 语言映射
        self.language_map = {
            '.py': 'python',
            '.js': 'javascript', '.jsx': 'javascript', '.ts': 'javascript', '.tsx': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp', '.cxx': 'cpp', '.cc': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust'
        }
    
    def can_parse(self, file_path: str) -> bool:
        """检查是否为支持的代码文件"""
        suffix = Path(file_path).suffix.lower()
        return suffix in self.language_map
    
    def parse(self, file_path: str) -> DocumentWithChunks:
        """解析代码文件"""
        doc_id = self._generate_doc_id(file_path)
        file_size = self._get_file_size(file_path)
        file_hash = self._calculate_file_hash(file_path)
        language = self._detect_language(file_path)
        
        # 创建文档对象
        document = DocumentWithChunks(
            doc_id=doc_id,
            file_path=file_path,
            file_type=DataSource.CODE,
            file_size_bytes=file_size,
            sha256_hash=file_hash
        )
        
        try:
            # 根据语言选择解析策略
            if language == 'python':
                chunks = self._parse_python_file(file_path, doc_id, language)
            elif language in ['javascript', 'typescript']:
                chunks = self._parse_javascript_file(file_path, doc_id, language)
            elif language == 'java':
                chunks = self._parse_java_file(file_path, doc_id, language)
            elif language in ['cpp', 'c']:
                chunks = self._parse_cpp_file(file_path, doc_id, language)
            else:
                # 通用文本解析
                chunks = self._parse_generic_code_file(file_path, doc_id, language)
            
            document.chunks = chunks
            document.processing_status = "completed"
            
        except Exception as e:
            document.processing_status = "failed"
            print(f"Error parsing code file {file_path}: {e}")
            # 回退到通用解析
            try:
                chunks = self._parse_generic_code_file(file_path, doc_id, language)
                document.chunks = chunks
                document.processing_status = "completed"
            except Exception as e2:
                print(f"Failed to parse with generic method: {e2}")
                raise
        
        return document
    
    def _detect_language(self, file_path: str) -> str:
        """检测代码语言"""
        suffix = Path(file_path).suffix.lower()
        return self.language_map.get(suffix, 'unknown')
    
    def _parse_python_file(self, file_path: str, doc_id: str, language: str) -> List[DocumentChunkWithMetadata]:
        """解析Python文件"""
        chunks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用AST解析
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    chunk = self._parse_python_function(node, content, file_path, doc_id, language)
                    if chunk:
                        chunks.append(chunk)
                elif isinstance(node, ast.ClassDef):
                    chunk = self._parse_python_class(node, content, file_path, doc_id, language)
                    if chunk:
                        chunks.append(chunk)
        
        except Exception as e:
            print(f"Failed to parse Python AST: {e}")
            # 回退到正则表达式解析
            chunks = self._parse_python_with_regex(file_path, doc_id, language)
        
        return chunks
    
    def _parse_python_function(self, node, source_code: str, file_path: str, 
                             doc_id: str, language: str) -> Optional[DocumentChunkWithMetadata]:
        """解析Python函数"""
        try:
            # 提取函数信息
            func_name = node.name
            start_line = node.lineno
            end_line = getattr(node, 'end_lineno', start_line)
            
            # 构建函数签名
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
            
            # 提取文档字符串
            docstring = ast.get_docstring(node) or ""
            
            # 提取注释
            comments = self._extract_python_comments(source_code, start_line, end_line)
            
            # 分析依赖
            dependencies = self._extract_python_dependencies(node)
            
            # 分析异常
            exceptions = self._extract_python_exceptions(node)
            
            # 构建函数描述
            func_desc = self._build_function_description(
                func_name, "函数", args, None, docstring, 
                comments, dependencies, exceptions
            )
            
            # 创建元数据
            signature = f"{func_name}({', '.join(args)})"
            code_metadata = CodeMetadata(
                language=language,
                file_path=file_path,
                symbol=func_name,
                signature=signature,
                line_start=start_line,
                line_end=end_line,
                symbol_type="function"
            )
            
            # 创建文档块
            chunk = DocumentChunkWithMetadata(
                doc_id=doc_id,
                content=func_desc,
                chunk_index=len([None]),  # 将在外部设置
                token_count=len(func_desc.split()),
                metadata={
                    "symbol": func_name,
                    "signature": signature,
                    "file_path": file_path,
                    "language": language,
                    "line_start": start_line,
                    "line_end": end_line,
                    "symbol_type": "function"
                },
                code_metadata=code_metadata
            )
            
            return chunk
            
        except Exception as e:
            print(f"Failed to parse Python function: {e}")
            return None
    
    def _parse_python_class(self, node, source_code: str, file_path: str,
                           doc_id: str, language: str) -> Optional[DocumentChunkWithMetadata]:
        """解析Python类"""
        try:
            # 提取类信息
            class_name = node.name
            start_line = node.lineno
            end_line = getattr(node, 'end_lineno', start_line)
            
            # 提取文档字符串
            docstring = ast.get_docstring(node) or ""
            
            # 提取方法
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)
            
            # 提取基类
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
            
            # 构建类描述
            class_desc = self._build_class_description(
                class_name, docstring, methods, bases
            )
            
            # 创建元数据
            signature = f"class {class_name}({', '.join(bases)})" if bases else f"class {class_name}"
            code_metadata = CodeMetadata(
                language=language,
                file_path=file_path,
                symbol=class_name,
                signature=signature,
                line_start=start_line,
                line_end=end_line,
                symbol_type="class"
            )
            
            # 创建文档块
            chunk = DocumentChunkWithMetadata(
                doc_id=doc_id,
                content=class_desc,
                chunk_index=0,  # 将在外部设置
                token_count=len(class_desc.split()),
                metadata={
                    "symbol": class_name,
                    "signature": signature,
                    "file_path": file_path,
                    "language": language,
                    "line_start": start_line,
                    "line_end": end_line,
                    "symbol_type": "class",
                    "methods": methods,
                    "bases": bases
                },
                code_metadata=code_metadata
            )
            
            return chunk
            
        except Exception as e:
            print(f"Failed to parse Python class: {e}")
            return None
    
    def _parse_python_with_regex(self, file_path: str, doc_id: str, language: str) -> List[DocumentChunkWithMetadata]:
        """使用正则表达式解析Python文件"""
        chunks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 正则表达式模式
            func_pattern = r'^\s*def\s+(\w+)\s*\([^)]*\)\s*:'
            class_pattern = r'^\s*class\s+(\w+)\s*(?:\([^)]*\))?\s*:'
            
            for line_num, line in enumerate(lines, 1):
                # 匹配函数
                func_match = re.match(func_pattern, line)
                if func_match:
                    func_name = func_match.group(1)
                    func_desc = self._build_simple_description(
                        func_name, "函数", line, line_num, file_path
                    )
                    
                    chunk = self._create_simple_code_chunk(
                        func_desc, func_name, line_num, doc_id, 
                        file_path, language, "function"
                    )
                    if chunk:
                        chunks.append(chunk)
                
                # 匹配类
                class_match = re.match(class_pattern, line)
                if class_match:
                    class_name = class_match.group(1)
                    class_desc = self._build_simple_description(
                        class_name, "类", line, line_num, file_path
                    )
                    
                    chunk = self._create_simple_code_chunk(
                        class_desc, class_name, line_num, doc_id,
                        file_path, language, "class"
                    )
                    if chunk:
                        chunks.append(chunk)
        
        except Exception as e:
            print(f"Failed to parse Python with regex: {e}")
        
        return chunks
    
    def _parse_javascript_file(self, file_path: str, doc_id: str, language: str) -> List[DocumentChunkWithMetadata]:
        """解析JavaScript文件"""
        chunks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # JavaScript正则表达式模式
            func_patterns = [
                r'^\s*function\s+(\w+)\s*\([^)]*\)\s*{',  // function name() {}
                r'^\s*const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{',  // const name = () => {}
                r'^\s*(\w+)\s*:\s*function\s*\([^)]*\)\s*{',  // name: function() {}
                r'^\s*(\w+)\s*\([^)]*\)\s*{',  // name() {} (method)
            ]
            
            for line_num, line in enumerate(lines, 1):
                for pattern in func_patterns:
                    match = re.match(pattern, line)
                    if match:
                        func_name = match.group(1)
                        func_desc = self._build_simple_description(
                            func_name, "函数", line, line_num, file_path
                        )
                        
                        chunk = self._create_simple_code_chunk(
                            func_desc, func_name, line_num, doc_id,
                            file_path, language, "function"
                        )
                        if chunk:
                            chunks.append(chunk)
                        break
        
        except Exception as e:
            print(f"Failed to parse JavaScript file: {e}")
        
        return chunks
    
    def _parse_java_file(self, file_path: str, doc_id: str, language: str) -> List[DocumentChunkWithMetadata]:
        """解析Java文件"""
        chunks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # Java正则表达式模式
            class_pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*class\s+(\w+)'
            method_pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:\w+)\s+(\w+)\s*\([^)]*\)\s*{'
            
            for line_num, line in enumerate(lines, 1):
                # 匹配类
                class_match = re.match(class_pattern, line)
                if class_match:
                    class_name = class_match.group(1)
                    class_desc = self._build_simple_description(
                        class_name, "类", line, line_num, file_path
                    )
                    
                    chunk = self._create_simple_code_chunk(
                        class_desc, class_name, line_num, doc_id,
                        file_path, language, "class"
                    )
                    if chunk:
                        chunks.append(chunk)
                
                # 匹配方法
                method_match = re.match(method_pattern, line)
                if method_match:
                    method_name = method_match.group(1)
                    method_desc = self._build_simple_description(
                        method_name, "方法", line, line_num, file_path
                    )
                    
                    chunk = self._create_simple_code_chunk(
                        method_desc, method_name, line_num, doc_id,
                        file_path, language, "method"
                    )
                    if chunk:
                        chunks.append(chunk)
        
        except Exception as e:
            print(f"Failed to parse Java file: {e}")
        
        return chunks
    
    def _parse_generic_code_file(self, file_path: str, doc_id: str, language: str) -> List[DocumentChunkWithMetadata]:
        """通用代码文件解析"""
        chunks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # 通用模式匹配
            patterns = {
                'cpp': [
                    r'^\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*{',  // 函数
                    r'^\s*class\s+(\w+)',  // 类
                ],
                'go': [
                    r'^\s*func\s+(\w+)\s*\([^)]*\)',  // 函数
                    r'^\s*type\s+(\w+)\s+struct',  // 结构体
                ],
                'rust': [
                    r'^\s*fn\s+(\w+)\s*\([^)]*\)',  // 函数
                    r'^\s*struct\s+(\w+)',  // 结构体
                ]
            }
            
            lang_patterns = patterns.get(language, patterns['cpp'])
            
            for line_num, line in enumerate(lines, 1):
                for pattern in lang_patterns:
                    match = re.match(pattern, line)
                    if match:
                        symbol_name = match.group(1)
                        
                        # 确定符号类型
                        symbol_type = "function"
                        if "class" in line or "struct" in line or "type" in line:
                            symbol_type = "class"
                        
                        desc = self._build_simple_description(
                            symbol_name, symbol_type, line, line_num, file_path
                        )
                        
                        chunk = self._create_simple_code_chunk(
                            desc, symbol_name, line_num, doc_id,
                            file_path, language, symbol_type
                        )
                        if chunk:
                            chunks.append(chunk)
                        break
        
        except Exception as e:
            print(f"Failed to parse generic code file: {e}")
        
        return chunks
    
    def _build_function_description(self, name: str, symbol_type: str, args: List[str], 
                                  return_type: Optional[str], docstring: str,
                                  comments: List[str], dependencies: List[str], 
                                  exceptions: List[str]) -> str:
        """构建函数描述"""
        desc_parts = [f"{symbol_type}：{name}"]
        
        # 参数描述
        if args:
            desc_parts.append(f"输入参数：{', '.join(args)}")
        
        # 返回类型
        if return_type:
            desc_parts.append(f"返回类型：{return_type}")
        
        # 功能描述
        if docstring:
            desc_parts.append(f"功能：{docstring}")
        
        # 副作用和依赖
        if dependencies:
            desc_parts.append(f"依赖：{', '.join(dependencies)}")
        
        # 异常处理
        if exceptions:
            desc_parts.append(f"可能抛出异常：{', '.join(exceptions)}")
        
        # 注释
        if comments:
            desc_parts.append(f"注释信息：{'; '.join(comments[:3])}")  # 限制注释数量
        
        return "。".join(desc_parts)
    
    def _build_class_description(self, name: str, docstring: str, methods: List[str], bases: List[str]) -> str:
        """构建类描述"""
        desc_parts = [f"类：{name}"]
        
        # 继承关系
        if bases:
            desc_parts.append(f"继承自：{', '.join(bases)}")
        
        # 功能描述
        if docstring:
            desc_parts.append(f"功能：{docstring}")
        
        # 方法列表
        if methods:
            desc_parts.append(f"包含方法：{', '.join(methods[:10])}")  # 限制方法数量
        
        return "。".join(desc_parts)
    
    def _build_simple_description(self, name: str, symbol_type: str, line: str, 
                                 line_num: int, file_path: str) -> str:
        """构建简单描述"""
        clean_line = line.strip()
        return f"{symbol_type}：{name}，定义位置：{Path(file_path).name}:{line_num}，声明：{clean_line}"
    
    def _extract_python_comments(self, source_code: str, start_line: int, end_line: int) -> List[str]:
        """提取Python代码中的注释"""
        comments = []
        lines = source_code.split('\n')
        
        for i in range(max(0, start_line - 5), min(len(lines), end_line + 5)):
            line = lines[i].strip()
            if line.startswith('#'):
                comment = line[1:].strip()
                if comment and len(comment) < 200:  # 过滤过长的注释
                    comments.append(comment)
        
        return comments
    
    def _extract_python_dependencies(self, node) -> List[str]:
        """提取Python代码的依赖"""
        dependencies = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    dependencies.append(alias.name)
            elif isinstance(child, ast.ImportFrom):
                module = child.module or ""
                for alias in child.names:
                    dependencies.append(f"{module}.{alias.name}")
        
        return list(set(dependencies))[:10]  # 去重并限制数量
    
    def _extract_python_exceptions(self, node) -> List[str]:
        """提取Python代码的异常"""
        exceptions = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc:
                    if isinstance(child.exc, ast.Name):
                        exceptions.append(child.exc.id)
                    elif isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                        exceptions.append(child.exc.func.id)
        
        return list(set(exceptions))
    
    def _create_simple_code_chunk(self, description: str, symbol_name: str, line_num: int,
                                 doc_id: str, file_path: str, language: str, symbol_type: str) -> Optional[DocumentChunkWithMetadata]:
        """创建简单代码块"""
        try:
            signature = f"{symbol_name}()"
            
            code_metadata = CodeMetadata(
                language=language,
                file_path=file_path,
                symbol=symbol_name,
                signature=signature,
                line_start=line_num,
                line_end=line_num,
                symbol_type=symbol_type
            )
            
            chunk = DocumentChunkWithMetadata(
                doc_id=doc_id,
                content=description,
                chunk_index=0,  # 将在外部设置
                token_count=len(description.split()),
                metadata={
                    "symbol": symbol_name,
                    "signature": signature,
                    "file_path": file_path,
                    "language": language,
                    "line_start": line_num,
                    "line_end": line_num,
                    "symbol_type": symbol_type
                },
                code_metadata=code_metadata
            )
            
            return chunk
            
        except Exception as e:
            print(f"Failed to create simple code chunk: {e}")
            return None
    
    def _generate_doc_id(self, file_path: str) -> str:
        """生成文档ID"""
        return f"code_{Path(file_path).stem}"