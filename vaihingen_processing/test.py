import os
import random
import re
import argparse

# 正则表达式
# data_dir = '/home/proof/hjl/dataset/GAMUS/images/test'
# regex = re.compile(r'(.*_)(\w+)\.(\w+)')
# list = os.listdir(data_dir)

# for item in list:
#     result = regex.search(item)
#     if result:
#         print(f"1:{result.group()}  2:{result.group(1)}  3:{result.group(2)}  4:{result.group(3)}")

def a():
    a = (1,2,3)
    print(a.shape)
    return a

a,b,c = a()
print(a,b,c)
