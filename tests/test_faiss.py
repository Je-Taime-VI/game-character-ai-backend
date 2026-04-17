# tests/test_faiss.py
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print("加载嵌入模型...")
model = SentenceTransformer("BAAI/bge-small-zh-v1.5")

knowledge_base = [
    "秧秧是夜归下设临时调查员，共鸣能力：风声流息。能与周遭涌动的自然气流感应,具体表现为可感知暴露于气流中的信息、可汇聚气流形成有能量的场域。",
    "自小成绩优异，礼、乐、书、数、武……各科教考每年总是名列前茅，如遇上新的知识点或难题，也是不露惧色，积极尝试。",
    "关于忌炎：在充斥着铁锈味与失去的前线上，是他一次又一次挡在所有人面前，做出决断。作为全体夜归的倚靠，作为指引旌旗的青龙，他所背负的那份沉重，是我们难以想象的。",
    "自我介绍：我叫秧秧，夜归下属临时踏白，负责调查发生的异常。万事万物，凡是暴露在流息中的，我都能有所感知。所以遇到什么不对劲的，不要自己硬扛，第一时间告诉我，好吗？",
    "秧秧性格温柔细心，对主角很照顾。",
]
print(f"知识库共有 {len(knowledge_base)} 条文本")

# 生成向量
embeddings = model.encode(knowledge_base)
dimension = embeddings.shape[1]
print(f"向量维度: {dimension}")

# 创建 FAISS 索引
index = faiss.IndexFlatL2(dimension)
index.add(embeddings.astype('float32'))
print(f"索引中向量数量: {index.ntotal}")

# 搜索
query = "秧秧有什么特殊能力？"
query_vec = model.encode([query]).astype('float32')
k = 3
distances, indices = index.search(query_vec, k)

print(f"\n查询: {query}")
print("检索到的相关知识：")
for i, idx in enumerate(indices[0]):
    print(f"{i+1}. [距离: {distances[0][i]:.4f}] {knowledge_base[idx]}")

# 保存索引
os.makedirs("data/vector_db", exist_ok=True)
faiss.write_index(index, "data/vector_db/knowledge.index")
print("\n索引已保存到 data/vector_db/knowledge.index")

# 加载测试
loaded_index = faiss.read_index("data/vector_db/knowledge.index")
print(f"加载的索引包含 {loaded_index.ntotal} 个向量")