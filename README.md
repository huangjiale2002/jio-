# 遥感数据处理工具集

一套用于遥感图像数据下载、预处理和数据集管理的 Python 工具集。

## 项目结构

```
.
├── download/                    # S3 数据下载工具
│   ├── download_linux.py
│   ├── download_linux_optimized.py  # 优化版（推荐）
│   ├── download_win.py
│   └── README.md
├── vaihingen_processing/        # 数据集处理工具
│   ├── vaihingen.py            # 主处理脚本
│   ├── split2.py               # 数据集划分工具
│   ├── test.py
│   └── README.md
└── README.md                    # 本文件
```

## 功能模块

### 1. 数据下载模块 (download/)

高性能的 S3 数据下载工具，支持断点续传和智能重试。

**核心特性**:
- ✅ 断点续传（大文件自动恢复）
- ✅ 智能重试（区分网络错误和文件错误）
- ✅ 并发下载（多线程加速）
- ✅ 实时进度显示（速度、进度、预估时间）
- ✅ 文件锁机制（防止多进程冲突）
- ✅ 磁盘空间检查
- ✅ 优雅退出（Ctrl+C）

**快速开始**:
```bash
# Linux 环境（推荐）
python download/download_linux_optimized.py \
    --bucket your-bucket \
    --prefix data/path/ \
    --output ./downloads \
    --workers 8

# Windows 环境
python download/download_win.py \
    --bucket your-bucket \
    --prefix data/path/ \
    --output ./downloads
```

详细文档：[download/README.md](download/README.md)

### 2. 数据处理模块 (vaihingen_processing/)

遥感图像数据集的预处理、切割、可视化和划分工具。

**支持的数据集**:
- Vaihingen（DSM + RGB + Label）
- Potsdam（DSM + RGB + Label）
- Gamus（DSM + RGB + Label）

**核心功能**:
- 🔪 图像切割（支持重叠切割）
- 🎨 可视化（Label RGB 转换、DSM 热力图）
- 📊 数据集划分（训练/验证/测试集）
- 📝 文件重命名和批量处理

**快速开始**:
```python
# 1. 数据切割
from vaihingen_processing.vaihingen import Vaihingen

v = Vaihingen(
    dataset_path='/path/to/raw/data',
    target_path='/path/to/output'
)
v.start_dealWith(split_size=512, cover_size=256)

# 2. 数据集划分
python vaihingen_processing/split2.py \
    -d /path/to/data/image \
    -r 0.8 0.1 0.1 \
    -o /path/to/output

# 3. 可视化
from vaihingen_processing.vaihingen import Visual_RGB

v = Visual_RGB(
    dataset_path='/path/to/data',
    target_path='/path/to/output'
)
v.Label2RGB()  # Label 彩色可视化
v.DSM2RGB()    # DSM 热力图
```

详细文档：[vaihingen_processing/README.md](vaihingen_processing/README.md)

## 安装依赖

### 下载模块
```bash
pip install boto3 botocore
```

### 处理模块
```bash
pip install numpy pillow tqdm
```

### 一键安装
```bash
pip install boto3 botocore numpy pillow tqdm
```

## 典型工作流程

### 完整的数据处理流程

```bash
# 步骤 1: 从 S3 下载原始数据
python download/download_linux_optimized.py \
    --bucket my-data-bucket \
    --prefix datasets/vaihingen/ \
    --output ./raw_data \
    --workers 8

# 步骤 2: 数据预处理和切割
python -c "
from vaihingen_processing.vaihingen import Vaihingen
v = Vaihingen('./raw_data', './processed_data')
v.start_dealWith(split_size=512, cover_size=256)
"

# 步骤 3: 数据集划分
python vaihingen_processing/split2.py \
    -d ./processed_data/image \
    -r 0.8 0.1 0.1 \
    -o ./data_split

# 步骤 4: 可视化（可选）
python -c "
from vaihingen_processing.vaihingen import Visual_RGB
v = Visual_RGB('./processed_data', './processed_data')
v.Label2RGB()
v.DSM2RGB()
"
```

## 数据格式

### 输入数据结构
```
raw_data/
├── DSM/          # 数字表面模型（Digital Surface Model）
├── RGB/          # RGB 遥感图像
└── Label/        # 标注图像
```

### 输出数据结构
```
processed_data/
├── DSM/          # 切割后的 DSM 块
├── RGB/          # 切割后的 RGB 块
├── Label/        # 切割后的 Label 块
├── DSM_RGB/      # DSM 可视化（可选）
└── Label_RGB/    # Label 可视化（可选）

data_split/
├── train.txt     # 训练集文件列表
├── val.txt       # 验证集文件列表
└── test.txt      # 测试集文件列表
```

## 配置说明

### 下载配置
- **并发数**: 根据网络带宽调整（推荐 4-16）
- **重试策略**: 网络错误几乎无限重试，文件错误最多3次
- **断点续传**: 大于 5MB 的文件自动启用

### 切割配置
- **split_size**: 切割块大小（如 512x512）
- **cover_size**: 重叠大小（如 256）
  - 步长 = split_size - cover_size
  - 重叠率 = cover_size / split_size

### 数据集划分
- **默认比例**: 训练集 80%，验证集 10%，测试集 10%
- **随机种子**: 42（确保可重复性）

## 系统要求

- **Python**: 3.6+
- **操作系统**: 
  - Linux（推荐，支持所有功能）
  - Windows（部分功能受限）
- **内存**: 建议 8GB+（处理大图像时）
- **磁盘**: 确保有足够空间（原始数据 + 切割后数据）

## 常见问题

### Q: 下载中断后如何恢复？
A: 直接重新运行下载命令，工具会自动检测已下载的文件并跳过，大文件会从断点继续。

### Q: 如何调整切割参数？
A: 根据模型输入大小设置 `split_size`，根据需要的上下文信息设置 `cover_size`（重叠区域）。

### Q: 支持哪些数据集？
A: 目前支持 Vaihingen、Potsdam 和 Gamus，可以通过继承基类扩展支持其他数据集。

### Q: 如何处理内存不足？
A: 减小 `split_size` 或减少并发下载的 `workers` 数量。

### Q: CSV 日志文件被占用怎么办？
A: 工具会自动写入备份文件（.backup），关闭占用程序后会恢复正常。

## 许可证

本项目仅供学习和研究使用。

## 贡献

欢迎提交 Issue 和 Pull Request。

## 联系方式

如有问题或建议，请通过 Issue 反馈。
