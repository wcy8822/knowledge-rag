import os
from FlagEmbedding import BGEM3FlagModel

model_path = os.path.expanduser('~/models/bge-m3/BAAI/bge-m3')

print(f"加载本地 BGE-M3 模型...")
print(f"模型路径: {model_path}")
print("=" * 60)

try:
    # 加载本地模型
    model = BGEM3FlagModel(model_path, use_fp16=True)
    print("✅ 模型加载成功！")

    # 测试编码中文文本
    test_docs = [
        "BGE-M3 是 BAAI 推出的最新嵌入模型，支持 100+ 种语言。",
        "FlagEmbedding 是使用 BGE 模型的官方 Python 库。",
        "长文档处理是 BGE-M3 的主要优势，最长支持 8192 tokens。"
    ]

    test_query = "BGE-M3 支持多少种语言？"

    # 编码文档
    print("\n编码文档...")
    doc_embeddings = model.encode(test_docs)
    print(f"✅ 编码成功！")
    print(f"   - 文档数量: 3")
    print(f"   - 向量维度: {doc_embeddings['dense_vecs'].shape}")
    print(f"   - 密集向量: ✅ {doc_embeddings['dense_vecs'].shape}")

    # 检查其他功能（可能不是所有版本都支持）
    try:
        print(f"   - 稀疏向量: {'✅ 支持' if doc_embeddings.get('sparse_vecs') is not None else '⚠️ 不支持'}")
    except:
        print(f"   - 稀疏向量: ⚠️ 不支持（正常）")

    try:
        print(f"   - 多向量: {'✅ 支持' if doc_embeddings.get('colbert_vecs') is not None else '⚠️ 不支持'}")
    except:
        print(f"   - 多向量: ⚠️ 不支持（正常）")

    # 编码查询
    print("\n编码查询...")
    query_embedding = model.encode([test_query])
    print(f"✅ 查询编码成功！")

    # 计算相似度
    import numpy as np
    scores = np.dot(query_embedding['dense_vecs'], doc_embeddings['dense_vecs'].T)[0]
    top_idx = np.argsort(scores)[-1]

    print(f"\n查询: {test_query}")
    print(f"最相关文档: {test_docs[top_idx]}")
    print(f"相似度分数: {scores[top_idx]:.4f}")

    print("\n" + "=" * 60)
    print("✅ BGE-M3 模型工作正常！可以开始构建 RAG 系统了")

except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    print("请检查模型路径或重新下载")
