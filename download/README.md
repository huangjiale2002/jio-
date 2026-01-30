# Download Linux Optimized

## 简介

`download_linux_optimized.py` 是一个功能强大的 S3 数据下载工具，专为 Linux 环境优化，支持断点续传、智能重试、并发下载和进度跟踪。

## 主要特性

### 核心功能
- **断点续传**: 支持大文件（>5MB）的断点续传，避免重复下载
- **智能重试**: 区分网络错误和文件错误，采用不同的重试策略
  - 网络错误：几乎无限重试（999999次），指数退避（5s → 10s → 30s → 1min → 5min）
  - 文件错误（404等）：最多重试3次后跳过
- **并发下载**: 使用线程池实现多文件并发下载
- **进度显示**: 大文件（>10MB）显示实时下载进度、速度和预估剩余时间

### 高级特性
- **文件锁机制**: 防止多进程同时下载同一文件
- **磁盘空间检查**: 下载前检查磁盘剩余空间（需要文件大小的2倍 + 10GB缓冲）
- **临时文件清理**: 自动清理超过48小时的历史临时文件
- **元数据校验**: 使用 ETag 和文件大小验证部分下载文件的完整性
- **CSV 批量写入**: 减少 I/O 操作，支持文件锁和备份机制
- **文件夹进度跟踪**: 统计和跟踪文件夹级别的下载进度

### 容错机制
- **优雅退出**: 捕获 Ctrl+C 信号，等待当前下载完成后退出
- **网络连接检测**: 自动检测网络连接状态
- **跨文件系统支持**: 安全的文件重命名，支持跨文件系统操作

## 配置参数

### 超时和重试
```python
MAX_NETWORK_RETRIES = 999999      # 网络错误重试次数
MAX_FILE_RETRIES = 3              # 文件错误重试次数
MAX_RETRY_TIME = 48 * 3600        # 单文件最大重试时间（48小时）
RETRY_DELAYS = [5, 10, 30, 60, 300]  # 重试延迟（秒）
DOWNLOAD_TIMEOUT = 600            # 单文件下载超时（10分钟）
```

### 文件处理
```python
PROGRESS_THRESHOLD = 10 * 1024 * 1024   # 10MB以上显示进度
RESUME_THRESHOLD = 5 * 1024 * 1024      # 5MB以上支持断点续传
TEMP_FILE_CLEANUP_AGE = 48 * 3600       # 临时文件清理时间（48小时）
MIN_DISK_SPACE_GB = 10                  # 最小磁盘剩余空间（10GB）
```

## 使用方法

### 基本用法
```bash
python download_linux_optimized.py \
    --bucket your-bucket-name \
    --prefix data/path/ \
    --output ./downloads \
    --workers 4
```

### 参数说明
- `--bucket`: S3 存储桶名称（必需）
- `--prefix`: S3 对象前缀/路径（可选）
- `--output`: 本地输出目录（默认：当前目录）
- `--workers`: 并发下载线程数（默认：4）
- `--csv`: CSV 日志文件路径（可选）
- `--progress-csv`: 文件夹进度统计 CSV 路径（可选）

### 示例

1. **下载整个文件夹**
```bash
python download_linux_optimized.py \
    --bucket my-data-bucket \
    --prefix datasets/images/ \
    --output ./data \
    --workers 8
```

2. **带进度跟踪**
```bash
python download_linux_optimized.py \
    --bucket my-data-bucket \
    --prefix datasets/ \
    --output ./data \
    --csv download_log.csv \
    --progress-csv folder_progress.csv
```

## 输出文件

### CSV 日志格式
```csv
timestamp_iso,bucket,key,size_bytes,size_human,etag,last_modified_iso,local_path,status
```

### 文件夹进度 CSV 格式
```csv
folder_path,total_files,total_size_bytes,total_size_human,downloaded_files,downloaded_size_bytes,downloaded_size_human,progress,last_update
```

## 错误处理

### 网络错误（可重试）
- 连接超时、连接拒绝
- 服务不可用（5xx 错误）
- 限流（429 错误）

### 文件错误（有限重试）
- 文件不存在（404）
- 访问被拒绝（403）
- 无效对象状态

## 注意事项

1. **磁盘空间**: 确保有足够的磁盘空间（文件大小的2倍 + 10GB缓冲）
2. **并发数**: 根据网络带宽和系统资源调整 `--workers` 参数
3. **临时文件**: 下载过程中会生成 `.tmp` 和 `.tmp.meta` 临时文件
4. **文件锁**: 使用 `.lock` 文件防止多进程冲突
5. **优雅退出**: 按 Ctrl+C 一次等待当前下载完成，按两次强制退出

## 依赖项

```bash
pip install boto3 botocore
```

## 系统要求

- Python 3.6+
- Linux 操作系统
- 支持 fcntl 文件锁（Linux/Unix）
