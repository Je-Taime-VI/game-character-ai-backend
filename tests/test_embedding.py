# tests/test_embedding.py
from sentence_transformers import SentenceTransformer
import numpy as np

# 可选：设置国内镜像（如果下载慢）
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print("正在加载嵌入模型 BAAI/bge-small-zh-v1.5 ...")
# 首次运行会自动下载模型（约30MB）
model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
print("模型加载成功！")

sentences = [
    "秧秧是夜归下设临时调查员，共鸣能力：风声流息。能与周遭涌动的自然气流感应,具体表现为可感知暴露于气流中的信息、可汇聚气流形成有能量的场域。",
    "秧秧的烦恼：虽然总想着为大家做到更多更多，但超出承受的限度……反而会给自己、给无法回馈的他人造成困扰吧？",
    "讨厌的食物:任何食物都该被好好对待吧？欸？黑，黑暗料理的话……"
]

print("正在生成向量...")
embeddings = model.encode(sentences)
print(f"向量形状: {embeddings.shape}")  # 应为 (3, 384)
print(f"第一个向量的前10个维度: {embeddings[0][:10]}")

# 计算相似度
similarities = model.similarity(embeddings, embeddings)
print("\n句子相似度矩阵:")
print(similarities)

# 模拟检索
query = "玩家问：在吃这方面有什么忌讳吗？"
query_vec = model.encode([query])
scores = model.similarity(query_vec, embeddings)[0]
most_similar_idx = np.argmax(scores)
print(f"\n查询: '{query}'")
print(f"最相似的已知句子: '{sentences[most_similar_idx]}'")
print(f"相似度分数: {scores[most_similar_idx]:.4f}")