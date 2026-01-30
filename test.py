import os
from collections import Counter

path = '/home/proof/hjl/CMG/dataset/data/AVE/data/trainSet.txt'
path2 = '/home/proof/hjl/CMG/dataset/data/AVE_OSCMG/trainSet_14.txt'
path3 = '/home/proof/hjl/CMG/dataset/data/AVE_OSCMG/trainSet_21.txt'
# 读取文件并统计类别
label_counter = Counter()

with open(path3, "r", encoding="utf-8") as f:
    for line in f:
        label = line.strip().split()[0].split('&')[0]  # 提取每行的第一个字段（标签）
        label_counter.update([label])  # 更新计数器

# 输出统计结果
print("类别统计：")
for label, count in label_counter.items():
    print(f"{label}: {count} 次")

print("\n总类别数：", len(label_counter))