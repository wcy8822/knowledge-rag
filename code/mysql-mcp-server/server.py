#!/usr/bin/env python3
"""MySQL MCP Server — 标准化数据库查询服务
功能: 只读SQL查询 / NL2SQL / 字段反查 / 表结构描述 / 执行计划
协议: MCP stdio 模式
配置: config.yaml
"""

import json
import sys
import os
import re
import urllib.request
from pathlib import Path
from datetime import datetime

# ============================================================
# 配置加载
# ============================================================

def load_config():
    """加载 config.yaml"""
    import yaml
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

try:
    import yaml
    CFG = load_config()
except ImportError:
    # yaml 不可用时用内置默认值
    CFG = None

HOME = Path.home()

def _get_password():
    """读取 MySQL 密码：优先环境变量，其次 ~/.secrets.env"""
    key = CFG['connection']['password_env_key'] if CFG else 'MYSQL_ROOT_PASSWORD'
    # 优先从环境变量读取
    val = os.environ.get(key)
    if val:
        return val
    # 回退到 ~/.secrets.env
    secrets_file = HOME / ".secrets.env"
    if secrets_file.exists():
        for line in secrets_file.read_text().splitlines():
            if line.startswith(f"export {key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

def _get_conn_params(database=None):
    """获取连接参数"""
    if CFG:
        c = CFG['connection']
        params = dict(host=c['host'], port=c.get('port', 3306), user=c['user'],
                      password=_get_password(), charset=c['charset'],
                      connect_timeout=c.get('connect_timeout', 10))
    else:
        params = dict(host='localhost', user='root', password=_get_password(), charset='utf8mb4')
    if database:
        params['database'] = database
    return params

# ============================================================
# 审计日志
# ============================================================

def _audit_log(tool, database, sql_preview):
    """记录审计日志"""
    if CFG and not CFG.get('audit', {}).get('enabled', False):
        return
    log_file = Path(os.path.expanduser(
        CFG['audit']['log_file'] if CFG else '~/.allin_ai_safe/mysql-mcp-audit.log'))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    preview = sql_preview.replace('\n', ' ')[:200]
    with open(log_file, 'a') as f:
        f.write(f"{ts} | {tool} | {database or '-'} | {preview}\n")

# ============================================================
# 安全检查
# ============================================================

def _security_check(sql):
    """SQL 安全检查，返回 (ok, error_msg)"""
    sql_upper = sql.strip().upper()

    # 只允许特定语句
    allowed = ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']
    if not any(sql_upper.startswith(s) for s in allowed):
        return False, f"只允许 {'/'.join(allowed)} 语句"

    # 阻止危险关键字
    blocked = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE']
    clean = sql_upper.split('--')[0].split('/*')[0]
    for kw in blocked:
        if kw in clean:
            return False, f"检测到 {kw} 关键字，禁止执行"

    # 长度检查
    max_len = CFG['limits']['max_query_length'] if CFG else 4096
    if len(sql) > max_len:
        return False, f"SQL 超过长度限制 ({len(sql)} > {max_len})"

    return True, ""

# ============================================================
# 表→库映射 & SQL 修正
# ============================================================

def _get_table_db_map():
    if CFG and 'table_to_db' in CFG:
        return CFG['table_to_db']
    return {}

def _get_db_aliases():
    if CFG and 'db_aliases' in CFG:
        return CFG['db_aliases']
    return {}

FIELD_REGEX_FIXES = [
    (r'\bwash_car_service\b', 'service_carwash_available'),
    (r'\bconvenience_store\b(?!_available)', 'convenience_store_available'),
]

def fix_sql(sql, db):
    """自动修正 SQL 和数据库名"""
    table_to_db = _get_table_db_map()
    db_aliases = _get_db_aliases()

    # 修正数据库别名
    if db in db_aliases:
        db = db_aliases[db]

    # 从 SQL 提取表名
    table_refs = re.findall(r'(?:FROM|JOIN)\s+(?:\w+\.)?(\w+)', sql, re.I)
    for table in table_refs:
        if table in table_to_db:
            correct_db = table_to_db[table]
            if db != correct_db:
                db = correct_db
                break

    # 修正跨库引用
    for table, correct_db in table_to_db.items():
        sql = re.sub(
            rf'\b(?:data_warehouse|data_manager|gas_dw|am_bi_dev|data_manager_db)\.{table}\b',
            f'{correct_db}.{table}', sql)

    # MySQL 语法修正
    sql = re.sub(r'DATE_SUB\(CURRENT_DATE,\s*(\d+)\)', r'DATE_SUB(CURDATE(), INTERVAL \1 DAY)', sql)
    sql = sql.replace('GETDATE()', 'CURDATE()')

    # 字段修正
    for pattern, replacement in FIELD_REGEX_FIXES:
        sql = re.sub(pattern, replacement, sql)

    # 跨库自动全限定
    table_dbs = set()
    for table in table_refs:
        if table in table_to_db:
            table_dbs.add(table_to_db[table])
    if len(table_dbs) > 1:
        for table in table_refs:
            if table in table_to_db:
                correct = table_to_db[table]
                sql = re.sub(rf'(FROM|JOIN)\s+(?![\w]+\.){table}\b',
                             rf'\1 {correct}.{table}', sql, flags=re.I)

    return sql, db

# ============================================================
# 工具实现
# ============================================================

def tool_query(sql, database="data_manager_db"):
    """执行只读 SQL 查询"""
    import pymysql

    ok, err = _security_check(sql)
    if not ok:
        return f"安全拦截: {err}"

    sql, database = fix_sql(sql, database)
    _audit_log('query', database, sql)

    max_rows = CFG['limits']['max_rows'] if CFG else 100
    timeout = CFG['limits']['query_timeout'] if CFG else 30

    try:
        params = _get_conn_params(database)
        params['read_timeout'] = timeout
        conn = pymysql.connect(**params)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows)
        total = cur.rowcount
        conn.close()

        if not rows:
            return f"查询成功但无结果 (数据库: {database})"

        result = f"数据库: {database} | 返回 {len(rows)}/{total} 行 | {len(columns)} 列\n\n"
        result += " | ".join(columns) + "\n"
        result += "-" * 60 + "\n"
        for row in rows[:20]:
            result += " | ".join(str(v)[:30] if v is not None else "NULL" for v in row) + "\n"
        if len(rows) > 20:
            result += f"... 还有 {len(rows)-20} 行\n"
        return result
    except Exception as e:
        return f"查询错误: {e}"


def tool_nl2sql(question):
    """自然语言转 SQL 并执行"""
    if CFG:
        nl = CFG.get('nl2sql', {})
        api_url = nl.get('llm_api', 'http://localhost:11434/api/generate')
        model = nl.get('llm_model', 'qwen2.5:7b')
        ctx_file = Path(os.path.expanduser(nl.get('context_file', '~/.allin_ai_safe/nl2sql-context.md')))
    else:
        api_url = 'http://localhost:11434/api/generate'
        model = 'qwen2.5:7b'
        ctx_file = HOME / '.allin_ai_safe/nl2sql-context.md'

    if not ctx_file.exists():
        return "NL2SQL context 文件不存在"

    context = ctx_file.read_text(errors='ignore')
    prompt = f"{context}\n\n## 用户问题\n{question}\n\n请生成 SQL，返回 JSON: {{\"sql\": \"...\", \"database\": \"...\"}}"

    _audit_log('nl2sql', '-', question)

    data = json.dumps({"model": model, "prompt": prompt, "stream": False,
                        "options": {"num_predict": 512, "temperature": 0.1}}).encode()
    try:
        req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read()).get("response", "").strip()
        match = re.search(r'\{[^}]+\}', result, re.DOTALL)
        if match:
            sql_info = json.loads(match.group())
            sql = sql_info.get("sql", "").strip()
            sql = "\n".join(l for l in sql.split("\n") if not l.strip().startswith("--"))
            db = sql_info.get("database", "data_manager_db")
            sql, db = fix_sql(sql, db)

            exec_result = tool_query(sql, db)

            # 失败时智能重试
            if exec_result.startswith("查询错误:") or exec_result.startswith("安全拦截:"):
                table_info = _get_table_columns_for_retry(sql, db)
                retry_prompt = f"""上一次 SQL 执行失败。
错误: {exec_result[:200]}
原SQL: {sql}
数据库: {db}

{table_info}

请基于【实际字段列表】修正 SQL。返回 JSON: {{"sql": "...", "database": "..."}}"""
                retry_data = json.dumps({"model": model, "prompt": retry_prompt, "stream": False,
                                         "options": {"num_predict": 512, "temperature": 0.1}}).encode()
                try:
                    rreq = urllib.request.Request(api_url, data=retry_data, headers={"Content-Type": "application/json"})
                    rresp = urllib.request.urlopen(rreq, timeout=180)
                    rresult = json.loads(rresp.read()).get("response", "").strip()
                    rmatch = re.search(r'\{[^}]+\}', rresult, re.DOTALL)
                    if rmatch:
                        rinfo = json.loads(rmatch.group())
                        sql2 = "\n".join(l for l in rinfo.get("sql", "").split("\n") if not l.strip().startswith("--"))
                        db2 = rinfo.get("database", db)
                        sql2, db2 = fix_sql(sql2, db2)
                        exec2 = tool_query(sql2, db2)
                        if not exec2.startswith("查询错误:") and not exec2.startswith("安全拦截:"):
                            return f"问题: {question}\nSQL: {sql2}\n数据库: {db2}\n(重试成功)\n\n{exec2}"
                except:
                    pass

            return f"问题: {question}\nSQL: {sql}\n数据库: {db}\n\n{exec_result}"
        return f"LLM 未能生成有效 SQL。原始输出:\n{result[:500]}"
    except Exception as e:
        return f"NL2SQL 错误: {e}"


def _get_table_columns_for_retry(sql, db):
    """查询实际字段列表用于重试"""
    import pymysql
    table_to_db = _get_table_db_map()
    tables = re.findall(r'(?:FROM|JOIN)\s+(?:\w+\.)?(\w+)', sql, re.I)
    parts = []
    for table in set(tables):
        actual_db = table_to_db.get(table, db)
        try:
            conn = pymysql.connect(**_get_conn_params(actual_db))
            cur = conn.cursor()
            cur.execute(f"SHOW COLUMNS FROM `{table}`")
            cols = [r[0] for r in cur.fetchall()]
            conn.close()
            parts.append(f"【{actual_db}.{table}】: {', '.join(cols)}")
        except:
            parts.append(f"【{table}】: 不存在于 {actual_db}")
    return "\n".join(parts) if parts else "无法获取表字段"


def tool_search_fields(fields, min_match=3):
    """字段反查：找出包含指定字段的所有表"""
    import pymysql
    _audit_log('search_fields', '-', f"fields={fields}")

    try:
        conn = pymysql.connect(**_get_conn_params())
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(fields))
        cur.execute(f"""
            SELECT TABLE_SCHEMA, TABLE_NAME,
                   GROUP_CONCAT(COLUMN_NAME ORDER BY COLUMN_NAME) as matched_cols,
                   COUNT(*) as match_count
            FROM information_schema.COLUMNS
            WHERE COLUMN_NAME IN ({placeholders})
              AND TABLE_SCHEMA NOT IN ('information_schema','mysql','performance_schema','sys')
            GROUP BY TABLE_SCHEMA, TABLE_NAME
            HAVING COUNT(*) >= %s
            ORDER BY match_count DESC, TABLE_SCHEMA, TABLE_NAME
            LIMIT 30
        """, fields + [min_match])
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return f"未找到包含 >={min_match} 个指定字段的表\n字段: {', '.join(fields)}"

        result = f"包含指定字段的表（按匹配数降序，最少{min_match}个）:\n"
        result += f"查询字段: {', '.join(fields)}\n\n"
        for db, table, cols, cnt in rows:
            result += f"[{cnt}/{len(fields)}] {db}.{table}\n"
            result += f"  匹配: {cols}\n\n"
        return result
    except Exception as e:
        return f"错误: {e}"


def tool_list_tables(database="data_manager_db"):
    """列出数据库的所有表和行数"""
    import pymysql
    _audit_log('list_tables', database, 'LIST')

    try:
        conn = pymysql.connect(**_get_conn_params())
        cur = conn.cursor()
        cur.execute(f"""
            SELECT table_name, table_rows, ROUND((data_length+index_length)/1024/1024,1) AS mb,
                   table_comment
            FROM information_schema.tables
            WHERE table_schema='{database}'
            ORDER BY table_rows DESC
        """)
        rows = cur.fetchall()
        conn.close()

        result = f"数据库 {database} 共 {len(rows)} 张表:\n\n"
        result += "表名 | 行数 | MB | 说明\n"
        result += "-" * 70 + "\n"
        for name, cnt, mb, comment in rows:
            c = f" | {comment}" if comment else ""
            result += f"{name} | {cnt:,} | {mb}{c}\n"
        return result
    except Exception as e:
        return f"错误: {e}"


def tool_describe(table, database=None):
    """表结构描述：字段、类型、注释、索引"""
    import pymysql
    table_to_db = _get_table_db_map()

    if not database:
        database = table_to_db.get(table, 'data_manager_db')

    _audit_log('describe', database, f"DESCRIBE {table}")

    try:
        conn = pymysql.connect(**_get_conn_params(database))
        cur = conn.cursor()

        # 表注释
        cur.execute(f"""
            SELECT table_comment, table_rows
            FROM information_schema.tables
            WHERE table_schema='{database}' AND table_name='{table}'
        """)
        tinfo = cur.fetchone()
        comment = tinfo[0] if tinfo and tinfo[0] else ''
        row_count = tinfo[1] if tinfo else 0

        # 字段
        cur.execute(f"""
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA='{database}' AND TABLE_NAME='{table}'
            ORDER BY ORDINAL_POSITION
        """)
        cols = cur.fetchall()

        # 索引
        cur.execute(f"SHOW INDEX FROM `{table}`")
        indexes = cur.fetchall()
        conn.close()

        result = f"表: {database}.{table}"
        if comment:
            result += f" — {comment}"
        result += f"\n行数: {row_count:,}\n"
        result += f"字段数: {len(cols)}\n\n"

        result += "字段 | 类型 | 可空 | 默认值 | 注释\n"
        result += "-" * 80 + "\n"
        for name, ctype, nullable, default, ccomment in cols:
            parts = [name, ctype, nullable]
            parts.append(str(default)[:20] if default else '-')
            parts.append(ccomment if ccomment else '')
            result += " | ".join(parts) + "\n"

        if indexes:
            result += f"\n索引 ({len(indexes)}):\n"
            seen = set()
            for idx in indexes:
                key_name = idx[2]
                if key_name not in seen:
                    seen.add(key_name)
                    unique = "UNIQUE " if not idx[1] else ""
                    result += f"  {unique}{key_name}\n"

        return result
    except Exception as e:
        return f"错误: {e}"


def tool_explain(sql, database="data_manager_db"):
    """SQL 执行计划分析"""
    import pymysql

    sql, database = fix_sql(sql, database)
    explain_sql = f"EXPLAIN {sql}" if not sql.strip().upper().startswith("EXPLAIN") else sql

    _audit_log('explain', database, explain_sql)

    try:
        conn = pymysql.connect(**_get_conn_params(database))
        cur = conn.cursor()
        cur.execute(explain_sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        conn.close()

        result = f"执行计划 ({database}):\n\n"
        result += " | ".join(columns) + "\n"
        result += "-" * 80 + "\n"
        for row in rows:
            result += " | ".join(str(v) if v is not None else "NULL" for v in row) + "\n"
        return result
    except Exception as e:
        return f"错误: {e}"


# ============================================================
# MCP Protocol
# ============================================================

def send_response(id, result):
    msg = json.dumps({"jsonrpc": "2.0", "id": id, "result": result})
    sys.stdout.write(f"Content-Length: {len(msg.encode())}\r\n\r\n{msg}")
    sys.stdout.flush()

def send_error(id, code, message):
    msg = json.dumps({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}})
    sys.stdout.write(f"Content-Length: {len(msg.encode())}\r\n\r\n{msg}")
    sys.stdout.flush()

TOOLS = [
    {
        "name": "query",
        "description": "在本地 MySQL 执行只读 SQL 查询。支持 SELECT/SHOW/DESCRIBE。自动修正数据库名和跨库引用。可查商户画像(data_manager_db)、油价(priceDB)、数仓(gas_dw)、BI(am_bi_dev)等库。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL 查询语句（仅 SELECT/SHOW/DESCRIBE）"},
                "database": {"type": "string", "description": "数据库名，默认 data_manager_db", "default": "data_manager_db"}
            },
            "required": ["sql"]
        }
    },
    {
        "name": "nl2sql",
        "description": "用自然语言查询数据库。自动将中文问题转为SQL并执行。例如：'KA站点有多少' '各省区重叠站数量' '标签覆盖率趋势'。失败会自动重试修正。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "自然语言问题，中文"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "search_fields",
        "description": "用字段名反查数据库，找出包含这些字段的所有表（按匹配数降序）。用于精确定位业务概念对应的源头表。例如：传入['brand_level','open_24h']定位商户画像核心表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fields": {"type": "array", "items": {"type": "string"}, "description": "字段名列表"},
                "min_match": {"type": "integer", "description": "最少匹配字段数，默认3", "default": 3}
            },
            "required": ["fields"]
        }
    },
    {
        "name": "list_tables",
        "description": "列出指定数据库的所有表、行数、大小和注释。用于了解数据库结构。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "description": "数据库名，默认 data_manager_db", "default": "data_manager_db"}
            }
        }
    },
    {
        "name": "describe_table",
        "description": "查看表的完整结构：字段名、类型、注释、索引。自动识别表所在数据库。用于理解表结构和字段含义。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "表名"},
                "database": {"type": "string", "description": "数据库名（可选，自动识别）"}
            },
            "required": ["table"]
        }
    },
    {
        "name": "explain_sql",
        "description": "分析 SQL 执行计划。用于优化慢查询、检查索引使用情况。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "要分析的 SQL"},
                "database": {"type": "string", "description": "数据库名，默认 data_manager_db", "default": "data_manager_db"}
            },
            "required": ["sql"]
        }
    },
]

def handle_request(request):
    method = request.get("method")
    id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        send_response(id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "mysql-query", "version": "1.0.0"},
            "capabilities": {"tools": {}}
        })
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send_response(id, {"tools": TOOLS})
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        try:
            if tool_name == "query":
                result = tool_query(args["sql"], args.get("database", "data_manager_db"))
            elif tool_name == "nl2sql":
                result = tool_nl2sql(args["question"])
            elif tool_name == "search_fields":
                result = tool_search_fields(args["fields"], args.get("min_match", 3))
            elif tool_name == "list_tables":
                result = tool_list_tables(args.get("database", "data_manager_db"))
            elif tool_name == "describe_table":
                result = tool_describe(args["table"], args.get("database"))
            elif tool_name == "explain_sql":
                result = tool_explain(args["sql"], args.get("database", "data_manager_db"))
            else:
                send_error(id, -32601, f"Unknown tool: {tool_name}")
                return
            send_response(id, {"content": [{"type": "text", "text": result}]})
        except Exception as e:
            send_response(id, {"content": [{"type": "text", "text": f"错误: {e}"}], "isError": True})
    elif method == "ping":
        send_response(id, {})
    else:
        if id is not None:
            send_error(id, -32601, f"Unknown method: {method}")


def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode().strip()
        if not line:
            break
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip()] = val.strip()
    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None
    body = sys.stdin.buffer.read(content_length)
    return json.loads(body.decode())


def main():
    while True:
        try:
            request = read_message()
            if request is None:
                break
            handle_request(request)
        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
