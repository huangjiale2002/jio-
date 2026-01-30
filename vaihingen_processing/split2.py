import os
import random
import re
import argparse

def split_dataset(data_dir, ratios=(0.8, 0.1, 0.1), output_dir='.'):
    """
    划分数据集并生成文件列表
    
    参数:
    data_dir: 数据文件所在目录
    ratios: 训练集、验证集、测试集的比例 (train_ratio, val_ratio, test_ratio)
    output_dir: 输出文件目录
    """
    
    # 验证比例总和为1.0
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError("比例总和必须为1.0")
    
    # 获取所有符合条件的文件名
    pattern = re.compile(r'scene_(\d{4})_(IMG|BLG|AGL)\.(png|tif)$', re.IGNORECASE)

    files = sorted([
        f for f in os.listdir(data_dir) 
        if pattern.match(f)
    ],key = lambda x : int(pattern.match(x).group(1))
    )
    
    if not files:
        print("未找到scene_xxxx格式的文件")
        return
    
    # 提取所有唯一的场景ID（避免不同后缀的相同场景被拆分）
    scene_ids = sorted({pattern.match(f).group(1) for f in files})

    random_seed = 42
    random.seed(random_seed)
    random.shuffle(scene_ids)
    
    # 计算划分点
    n = len(scene_ids)
    train_end = int(n * ratios[0])
    val_end = train_end + int(n * ratios[1])
    
    # 划分数据集
    train_ids = scene_ids[:train_end]
    val_ids = scene_ids[train_end:val_end]
    test_ids = scene_ids[val_end:]
    
    # 生成文件名前缀（格式: scene_xxxx）
    def format_name(scene_id):
        return f"scene_{int(scene_id):04d}"
    
    # 写入文件
    def write_list(filepath, ids):
        with open(filepath, 'w') as f:
            for scene_id in sorted(ids):  # 按数字排序写入
                f.write(format_name(scene_id) + '\n')
    
    os.makedirs(output_dir, exist_ok=True)
    write_list(os.path.join(output_dir, 'train.txt'), train_ids)
    write_list(os.path.join(output_dir, 'val.txt'), val_ids)
    write_list(os.path.join(output_dir, 'test.txt'), test_ids)
    
    print(f"数据集划分完成：")
    print(f"训练集: {len(train_ids)}个场景 ({100*ratios[0]:.1f}%)")
    print(f"验证集: {len(val_ids)}个场景 ({100*ratios[1]:.1f}%)")
    print(f"测试集: {len(test_ids)}个场景 ({100*ratios[2]:.1f}%)")
    print(f"文件列表已保存至: {output_dir}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='数据集划分工具')
    parser.add_argument('-d','--data_dir', type=str, default='/home/proof/hjl/HTC-DC-Net-main/data/image', 
                       help='数据文件目录 (默认:当前目录)')
    parser.add_argument('-r','--ratios', type=float, nargs=3, default=[0.8, 0.1, 0.1],
                       metavar=('TRAIN', 'VAL', 'TEST'),
                       help='划分比例 (默认: 0.8 0.1 0.1)')
    parser.add_argument('-o','--output', type=str, default='/home/proof/hjl/HTC-DC-Net-main/data_split', 
                       help='输出目录 (默认:当前目录)')
    args = parser.parse_args()
    
    split_dataset(
        data_dir=args.data_dir,
        ratios=args.ratios,
        output_dir=args.output
    )