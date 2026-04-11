from modelscope import snapshot_download
import os

# 创建本地模型目录
model_dir = os.path.expanduser('~/models/bge-m3')
os.makedirs(os.path.dirname(model_dir), exist_ok=True)

print(f"开始下载 BAAI/bge-m3 模型...")
print(f"目标目录: {model_dir}")
print("=" * 60)

# 从 ModelScope 下载模型（完整下载，约 4.7GB）
model_path = snapshot_download('BAAI/bge-m3', cache_dir=model_dir)

print("=" * 60)
print(f"✅ 下载完成！")
print(f"模型位置: {model_path}")

# 列出下载的文件
import os
files = os.listdir(model_path)
print(f"\n已下载的文件数量: {len(files)}")
print("文件列表:")
for f in sorted(files):
    file_path = os.path.join(model_path, f)
    size = os.path.getsize(file_path) / (1024**3)  # 转换为 GB
    print(f"  - {f}: {size:.2f} GB" if size > 0.1 else f"  - {f}")
