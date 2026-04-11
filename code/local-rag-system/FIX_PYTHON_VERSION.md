# 🔧 修复 local_knowledge MCP 服务的 Python 版本问题

## ❌ 问题说明

您的 `local_knowledge` MCP 服务无法启动，原因是：
- **当前 Python 版本**: 3.9.6
- **MCP 库要求**: Python >= 3.10
- **错误**: `ModuleNotFoundError: No module named 'mcp'`

## ✅ 解决方案（3选1）

### 方案1：安装 Homebrew 并升级 Python（推荐）⭐

```bash
# 1. 安装 Homebrew（如果还没安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装 Python 3.11
brew install python@3.11

# 3. 验证安装
/opt/homebrew/bin/python3.11 --version

# 4. 更新 .claude.json 中的 local_knowledge 配置
# 将 "command": "python3" 改为 "command": "/opt/homebrew/bin/python3.11"
```

### 方案2：从 Python.org 下载并安装

```bash
# 1. 访问官网下载 Python 3.11+
# https://www.python.org/downloads/macos/

# 2. 安装后，Python通常在以下位置：
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11

# 3. 验证
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 --version

# 4. 更新 .claude.json（使用新路径）
```

### 方案3：使用 Pyenv（开发者推荐）

```bash
# 1. 安装 pyenv
curl https://pyenv.run | bash

# 2. 添加到 shell 配置
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# 3. 重启终端或重新加载配置
source ~/.zshrc

# 4. 安装 Python 3.11
pyenv install 3.11.7
pyenv global 3.11.7

# 5. 验证
python3 --version

# 6. .claude.json 可以保持使用 "python3"（因为 pyenv 会自动处理）
```

---

## 📝 安装完成后的配置步骤

### 步骤1：安装 MCP 库

```bash
# 使用新的 Python 安装 mcp 库
/opt/homebrew/bin/python3.11 -m pip install mcp

# 或者如果使用官方安装：
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m pip install mcp
```

### 步骤2：更新 .claude.json

打开 `~/.claude.json`，找到 local_knowledge 配置，更新为：

```json
"local_knowledge": {
  "command": "/opt/homebrew/bin/python3.11",  // ← 使用新的Python路径
  "args": [
    "/Users/didi/Downloads/panth/local-rag-system/src/serve/mcp_knowledge_server.py"
  ],
  "env": {
    "KNOWLEDGE_DB_PATH": "/Users/didi/Downloads/panth/data/chroma",
    "PYTHONPATH": "/Users/didi/Downloads/panth/local-rag-system"
  }
}
```

### 步骤3：重启 Claude Code

```bash
# 退出 Claude Code 并重新打开
# 或者在新的终端窗口中启动
```

### 步骤4：验证服务状态

在 Claude Code 中查看 MCP 服务状态：
- 应该看到 `local_knowledge` 显示为 ✅ **connected**

---

## 🧪 测试 local_knowledge 服务

启动成功后，你可以直接在对话中问 Claude：

```
"搜索我的本地知识库关于 [话题] 的信息"
```

Claude 会自动调用 `search_knowledge` 工具，从你的本地向量数据库中检索相关信息！

---

## ⚡ 快速命令参考

```bash
# 检查当前 Python 版本
python3 --version

# 查找所有 Python 安装
which -a python3 python3.10 python3.11 python3.12

# 测试 MCP 服务（手动）
/opt/homebrew/bin/python3.11 /Users/didi/Downloads/panth/local-rag-system/src/serve/mcp_knowledge_server.py --help

# 安装 MCP 依赖
/opt/homebrew/bin/python3.11 -m pip install mcp chromadb sentence-transformers
```

---

## ❓ 常见问题

### Q: 为什么不直接升级系统 Python？
A: macOS 系统 Python (在 `/usr/bin/python3`) 不建议修改，因为系统工具可能依赖它。

### Q: 我安装了 Python 3.11，但还是失败？
A: 确保更新了 `.claude.json` 中的完整路径，不要使用 `python3` 别名。

### Q: 能否使用虚拟环境？
A: 可以！创建 venv 后，在 `.claude.json` 中指向 venv 的 Python：
```bash
python3.11 -m venv ~/.venvs/mcp_env
# 然后在配置中使用: ~/.venvs/mcp_env/bin/python3
```

---

## 📊 预期结果

修复后的 MCP 服务状态：
```
✅ memory
✅ sequential-thinking
✅ filesystem
✅ playwright
✅ puppeteer
✅ brave-search
✅ everything
✅ local_knowledge  ← 新修复！
```

---

## 🎯 总结

1. ✅ **删除 sqlite 和 postgres** - 已完成（配置不正确）
2. ⏳ **修复 local_knowledge** - 需要安装 Python 3.10+
3. 🚀 **启用本地知识库** - 修复后可自动调用！

选择上面的任一方案，15分钟内即可完成修复！
