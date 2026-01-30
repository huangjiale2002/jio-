# Vaihingen Processing

## 简介

`vaihingen_processing` 是一个用于处理遥感图像数据集的工具集，支持 Vaihingen、Potsdam 和 Gamus 等数据集的预处理、切割、可视化和数据集划分。

## 文件说明

### vaihingen.py
主要的数据处理脚本，包含多个数据集处理类和可视化工具。

### split2.py
数据集划分工具，用于将数据集按比例划分为训练集、验证集和测试集。

### test.py
测试脚本，用于验证正则表达式和其他功能。

## 主要功能

### 1. 数据集处理类

#### Vaihingen 类
处理 Vaihingen 数据集（DSM + RGB + Label）

**特点**:
- 支持重叠切割（可配置切割大小和重叠大小）
- 自动对齐 DSM、RGB 和 Label 的尺寸
- RGB 标签转换为类别索引

**使用示例**:
```python
from vaihingen import Vaihingen

v = Vaihingen(
    dataset_path='/path/to/Vaihingen',
    target_path='/path/to/output'
)
v.start_dealWith(split_size=512, cover_size=256)
```

#### Potsdam 类
处理 Potsdam 数据集

**特点**:
- 自动匹配 DSM、RGB 和 Label 文件
- 使用正则表达式解析文件名
- 支持重叠切割

**使用示例**:
```python
from vaihingen import Potsdam

p = Potsdam(
    dataset_path='/path/to/Potsdam',
    target_path='/path/to/output'
)
p.start_dealWith(split_size=512, cover_size=256)
```

#### Gamus 类
处理 Gamus 数据集

**特点**:
- 支持多种 RGB 文件格式（RGB.jpg 或 IMG.jpg）
- 自动匹配对应的 DSM 和 Label 文件
- 输出格式可配置（PNG/JPG）

**使用示例**:
```python
from vaihingen import Gamus

g = Gamus(
    dataset_path='/path/to/Gamus',
    target_path='/path/to/output'
)
g.start_dealWith(split_size=512, cover_size=256)
```

### 2. 可视化工具

#### Visual_RGB 类
将 Label 和 DSM 转换为 RGB 可视化图像

**功能**:
- **Label2RGB**: 将类别标签转换为彩色图像
- **DSM2RGB**: 将 DSM 高度图转换为热力图

**使用示例**:
```python
from vaihingen import Visual_RGB

v = Visual_RGB(
    dataset_path='/path/to/data',
    target_path='/path/to/output'
)
v.Label2RGB()  # 生成 Label 的 RGB 可视化
v.DSM2RGB()    # 生成 DSM 的热力图可视化
```

**DSM 颜色映射**:
- `thermal`: 热成像色彩（黑色→深蓝→紫色→红色→黄色→白色）
- `jet`: 经典 Jet 色彩（蓝→青→绿→黄→红）
- 默认: 灰度图

### 3. 数据集划分工具 (split2.py)

将数据集按比例划分为训练集、验证集和测试集。

**使用方法**:
```bash
python split2.py \
    -d /path/to/data/image \
    -r 0.8 0.1 0.1 \
    -o /path/to/output
```

**参数说明**:
- `-d, --data_dir`: 数据文件目录（包含 scene_xxxx 格式的文件）
- `-r, --ratios`: 训练集、验证集、测试集的比例（默认：0.8 0.1 0.1）
- `-o, --output`: 输出目录（默认：当前目录）

**输出文件**:
- `train.txt`: 训练集文件列表
- `val.txt`: 验证集文件列表
- `test.txt`: 测试集文件列表

**文件格式**:
```
scene_0001
scene_0002
scene_0003
...
```

### 4. 文件重命名工具

#### Rename 类
批量重命名数据集文件

**使用示例**:
```python
from vaihingen import Rename

n = Rename('/path/to/dataset')
n.rename('all')  # 重命名所有文件
# 或
n.rename('RGB')    # 只重命名 RGB 文件
n.rename('Label')  # 只重命名 Label 文件
```

## 颜色映射

### Vaihingen 颜色映射
```python
Vaihingen_COLOR_MAP = [
    [255, 255, 255],  # 0: 不透水路面 (Impervious surfaces)
    [0, 0, 255],      # 1: 建筑物 (Building)
    [0, 255, 255],    # 2: 低植被 (Low vegetation)
    [0, 255, 0],      # 3: 树木 (Tree)
    [255, 255, 0],    # 4: 汽车 (Car)
    [255, 0, 0]       # 5: 背景 (Clutter/background)
]
```

## 数据集结构

### 输入结构
```
dataset/
├── DSM/          # 数字表面模型
├── RGB/          # RGB 图像
└── Label/        # 标签图像
```

### 输出结构
```
output/
├── DSM/          # 切割后的 DSM
├── RGB/          # 切割后的 RGB
├── Label/        # 切割后的 Label
├── DSM_RGB/      # DSM 可视化（可选）
└── Label_RGB/    # Label 可视化（可选）
```

## 切割参数说明

- **split_size**: 切割块的大小（如 512x512）
- **cover_size**: 重叠大小（如 256）
  - 实际步长 = split_size - cover_size
  - 例如：split_size=512, cover_size=256，则每次移动 256 像素

**计算公式**:
```python
range_x = ((min_x - split_size) // (split_size - cover_size)) + 1
range_y = ((min_y - split_size) // (split_size - cover_size)) + 1
```

## 依赖项

```bash
pip install numpy pillow tqdm
```

## 使用流程

### 完整处理流程

1. **数据预处理和切割**
```python
from vaihingen import Vaihingen

v = Vaihingen(
    dataset_path='/path/to/raw/data',
    target_path='/path/to/processed/data'
)
v.start_dealWith(split_size=512, cover_size=256)
```

2. **数据集划分**
```bash
python split2.py \
    -d /path/to/processed/data/image \
    -r 0.8 0.1 0.1 \
    -o /path/to/data_split
```

3. **可视化（可选）**
```python
from vaihingen import Visual_RGB

v = Visual_RGB(
    dataset_path='/path/to/processed/data',
    target_path='/path/to/processed/data'
)
v.Label2RGB()
v.DSM2RGB()
```

## 注意事项

1. **文件命名**: 确保输入文件遵循各数据集的命名规范
2. **内存使用**: 处理大图像时注意内存占用
3. **磁盘空间**: 切割后的数据量会显著增加
4. **随机种子**: split2.py 使用固定随机种子（42）确保可重复性
5. **文件格式**: 
   - Vaihingen: DSM 为 TIF，RGB 和 Label 为 PNG
   - Potsdam: 所有文件为 TIF
   - Gamus: DSM 和 Label 为 PNG，RGB 为 JPG

## 常见问题

### Q: 如何调整切割参数？
A: 根据模型输入大小调整 `split_size`，根据需要的重叠程度调整 `cover_size`。

### Q: 如何处理不同尺寸的图像？
A: 代码会自动取 DSM、RGB 和 Label 的最小尺寸进行切割。

### Q: 如何自定义颜色映射？
A: 修改 `Vaihingen_COLOR_MAP` 列表，或在 `DSM2RGB` 函数中添加新的 colormap。
