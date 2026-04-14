# Loki — 本地知识向量化系统

## MySQL 本地连接

- **Host**: localhost / **Port**: 3306 / **User**: root / **Socket**: /tmp/mysql.sock
- **Version**: 9.6.0
- **密码**: 环境变量 `$MYSQL_ROOT_PASSWORD`，定义在 `~/.secrets.env`
- **获取方式**: `source ~/.secrets.env && echo $MYSQL_ROOT_PASSWORD`
- **fallback**（无 shell 环境）: 解析 `~/.secrets.env` 中 `export MYSQL_ROOT_PASSWORD="..."` 行

```python
# Python 连接
import os, pymysql
# 优先环境变量，fallback 读 ~/.secrets.env
pw = os.environ.get('MYSQL_ROOT_PASSWORD', '')
if not pw:
    from pathlib import Path
    for line in Path.home().joinpath('.secrets.env').read_text().splitlines():
        if line.startswith('export MYSQL_ROOT_PASSWORD='):
            pw = line.split('=', 1)[1].strip().strip('"')
conn = pymysql.connect(host='localhost', user='root', password=pw, charset='utf8mb4')
```

```bash
# Shell 连接
source ~/.secrets.env && mysql -u root -p"$MYSQL_ROOT_PASSWORD"
```

**可用数据库**: am_bi_dev, data_manager_db, gas_dw, priceDB, XHDB, _archive, _staging

**安全约束**: 只允许 SELECT/SHOW/DESCRIBE，密码不写入代码或配置文件。
