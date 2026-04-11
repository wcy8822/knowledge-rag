import os
from pathlib import Path

model_path = os.path.expanduser('~/models/bge-m3/BAAI/bge-m3')

print("验证 BGE-M3 模型完整性...")
print("=" * 60)

# 必需文件清单
required_files = [
    'config.json',
    'pytorch_model.bin',
    'tokenizer.json',
    'tokenizer_config.json',
    'special_tokens_map.json',
    'sentencepiece.bpe.model'
]

all_present = True
for filename in required_files:
    file_path = os.path.join(model_path, filename)
    if os.path.exists(file_path):
        size = os.path.getsize(file_path)
        size_mb = size / (1024**2)
        status = "✅"
        print(f"{status} {filename:30s} ({size_mb:8.2f} MB)")
    else:
        status = "❌"
        print(f"{status} {filename:30s} (缺失)")
        all_present = False

print("=" * 60)
if all_present:
    print("✅ 所有文件完整！模型可以使用")
else:
    print("❌ 某些文件缺失，请重新下载")
