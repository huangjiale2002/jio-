import os, argparse, csv, datetime, time, signal, sys, threading, socket, shutil, hashlib, json, fcntl
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Optional, Tuple, Dict
from collections import defaultdict
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError, EndpointConnectionError, ConnectionError as BotoConnectionError

# 配置超时和重试
S3_CONFIG = Config(
    signature_version=UNSIGNED,
    connect_timeout=15,
    read_timeout=60,
    retries={'max_attempts': 2, 'mode': 'adaptive'}
)

# 重试配置
MAX_NETWORK_RETRIES = 999999  # 网络错误几乎无限重试
MAX_FILE_RETRIES = 3  # 文件错误（如404）只重试3次
MAX_RETRY_TIME = 48 * 3600  # 单文件最大重试时间：48小时
RETRY_DELAYS = [5, 10, 30, 60, 300]  # 指数退避：5s, 10s, 30s, 1min, 5min（之后保持5min）
CSV_BATCH_SIZE = 50
DOWNLOAD_TIMEOUT = 600  # 单文件下载超时（秒）
PROGRESS_THRESHOLD = 10 * 1024 * 1024  # 大于10MB的文件显示进度
RESUME_THRESHOLD = 5 * 1024 * 1024  # 大于5MB的文件支持断点续传
TEMP_FILE_CLEANUP_AGE = 48 * 3600  # 临时文件清理时间：48小时
MIN_DISK_SPACE_GB = 10  # 最小磁盘剩余空间（GB）

# 全局变量用于优雅退出
_shutdown_requested = False
_csv_writer = None

def signal_handler(signum, frame):
    """捕获信号，优雅退出"""
    global _shutdown_requested
    if _shutdown_requested:
        # 第二次信号强制退出
        print("\n强制退出...")
        if _csv_writer:
            try:
                # 兼容两种类型的 writer
                if hasattr(_csv_writer, 'write_csv'):
                    _csv_writer.write_csv(force=True)
                elif hasattr(_csv_writer, 'flush'):
                    _csv_writer.flush()
            except Exception:
                pass
        sys.exit(1)
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    print(f"\n收到信号 {sig_name}，等待当前下载完成后退出（再按一次强制退出）...")
    _shutdown_requested = True

def human(n: int) -> str:
    if n < 0:
        return "0 B"
    u = ["B","KB","MB","GB","TB"]; i=0; s=float(n)
    while s>=1024 and i<len(u)-1: s/=1024; i+=1
    return f"{s:.2f} {u[i]}"

def ensure_dir(p: str):
    d = os.path.dirname(p)
    if d:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            print(f"  创建目录失败 {d}: {e}")
            raise

def file_size_if_exists(path: str) -> int:
    """返回文件大小，不存在返回-1，其他错误返回-2"""
    try:
        return os.stat(path).st_size
    except FileNotFoundError:
        return -1
    except OSError:
        return -2  # 权限问题等

def is_network_error(e: Exception) -> bool:
    """判断是否为网络错误（可重试）"""
    # 明确的网络错误类型
    if isinstance(e, (EndpointConnectionError, BotoConnectionError, socket.timeout, socket.gaierror, 
                      TimeoutError, FuturesTimeoutError, ConnectionError, OSError)):
        # OSError 需要进一步检查 errno
        if isinstance(e, OSError):
            # 网络相关的 errno: ECONNREFUSED(111), ETIMEDOUT(110), ENETUNREACH(101), etc.
            if hasattr(e, 'errno') and e.errno in [110, 111, 101, 113]:
                return True
            return False
        return True
    
    if isinstance(e, ClientError):
        error_code = e.response.get('Error', {}).get('Code', '')
        # 明确的网络/服务器错误
        if error_code in ['RequestTimeout', 'ServiceUnavailable', 'SlowDown', 'InternalError', 
                          'RequestTimeTooSkewed', 'OperationAborted']:
            return True
        # 404, 403 等是文件错误，不是网络错误
        if error_code in ['NoSuchKey', 'AccessDenied', 'InvalidObjectState', 'NoSuchBucket']:
            return False
        status_code = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        if status_code >= 500:  # 5xx 服务器错误
            return True
        if status_code == 429:  # 限流
            return True
    
    # 最后才检查异常消息（避免误判）
    err_msg = str(e).lower()
    # 更严格的关键词匹配，避免误判文件名
    network_keywords = ['timed out', 'connection refused', 'connection reset', 
                       'network unreachable', 'host unreachable', 'connection aborted',
                       'connection error', 'socket error']
    if any(kw in err_msg for kw in network_keywords):
        return True
    
    return False

def check_network_connectivity(host: str = "s3.amazonaws.com", port: int = 443, timeout: int = 5) -> bool:
    """检查网络连接"""
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except (socket.timeout, socket.error):
        return False

def cleanup_temp_files(output_dir: str) -> int:
    """清理历史临时文件，返回清理数量"""
    count = 0
    try:
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                if f.endswith('.tmp') or f.endswith('.tmp.meta'):
                    tmp_path = os.path.join(root, f)
                    try:
                        # 检查文件修改时间，超过48小时的才删除
                        if time.time() - os.path.getmtime(tmp_path) > TEMP_FILE_CLEANUP_AGE:
                            # 检查是否有文件锁
                            if not is_file_locked(tmp_path):
                                os.remove(tmp_path)
                                count += 1
                    except OSError:
                        pass
    except OSError:
        pass
    return count

def is_file_locked(filepath: str) -> bool:
    """检查文件是否被锁定（正在使用）"""
    lock_file = filepath + '.lock'
    try:
        # 检查锁文件是否存在且新鲜（5分钟内）
        if os.path.exists(lock_file):
            if time.time() - os.path.getmtime(lock_file) < 300:
                return True
            else:
                # 过期的锁文件，删除
                try:
                    os.remove(lock_file)
                except OSError:
                    pass
        return False
    except OSError:
        return False

def create_file_lock(filepath: str) -> bool:
    """创建文件锁，返回是否成功"""
    lock_file = filepath + '.lock'
    try:
        # 使用 O_CREAT | O_EXCL 原子性创建
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return False

def remove_file_lock(filepath: str):
    """删除文件锁"""
    lock_file = filepath + '.lock'
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except OSError:
        pass

def get_disk_space(path: str) -> Tuple[int, int]:
    """获取磁盘空间（总空间，剩余空间），单位字节"""
    try:
        stat = shutil.disk_usage(path)
        return stat.total, stat.free
    except OSError:
        return 0, 0

def check_disk_space(path: str, required_bytes: int) -> bool:
    """检查磁盘空间是否足够"""
    _, free = get_disk_space(path)
    min_free = MIN_DISK_SPACE_GB * 1024**3
    return free >= (required_bytes + min_free)

def save_download_meta(temp_local: str, etag: str, size: int, downloaded: int):
    """保存下载元数据（用于断点续传校验）"""
    meta_file = temp_local + '.meta'
    try:
        meta = {
            'etag': etag,
            'size': size,
            'downloaded': downloaded,
            'timestamp': time.time()
        }
        with open(meta_file, 'w') as f:
            json.dump(meta, f)
    except (OSError, IOError):
        pass

def load_download_meta(temp_local: str) -> Optional[dict]:
    """加载下载元数据"""
    meta_file = temp_local + '.meta'
    try:
        if os.path.exists(meta_file):
            with open(meta_file, 'r') as f:
                return json.load(f)
    except (OSError, IOError, json.JSONDecodeError):
        pass
    return None

def verify_partial_file(temp_local: str, expected_size: int, etag: Optional[str]) -> bool:
    """验证部分下载文件的完整性"""
    if not os.path.exists(temp_local):
        return False
    
    actual_size = os.path.getsize(temp_local)
    if actual_size > expected_size:
        # 文件大小超过预期，损坏
        return False
    
    # 加载元数据
    meta = load_download_meta(temp_local)
    if meta:
        # 检查 ETag 是否匹配
        if etag and meta.get('etag') != etag:
            return False
        # 检查大小是否匹配
        if meta.get('size') != expected_size:
            return False
        if meta.get('downloaded') != actual_size:
            return False
    
    return True

def safe_rename(src: str, dst: str) -> bool:
    """安全重命名文件，支持跨文件系统"""
    try:
        # 先尝试直接重命名（同文件系统）
        os.rename(src, dst)
        return True
    except OSError as e:
        # 如果是跨文件系统错误，使用 copy + delete
        if e.errno == 18:  # EXDEV: Invalid cross-device link
            try:
                shutil.copy2(src, dst)
                os.remove(src)
                return True
            except (OSError, IOError):
                return False
        return False

class ProgressCallback:
    """下载进度回调，显示进度和网速"""
    def __init__(self, total_size: int, filename: str, initial: int = 0):
        self.total_size = max(total_size, 1)  # 防止除零
        self.filename = filename
        self.downloaded = initial  # 支持断点续传
        self.start_time = time.time()
        self.last_print_time = 0
        self.last_downloaded = initial
        self._lock = threading.Lock()  # 线程安全
    
    def __call__(self, bytes_amount):
        with self._lock:
            self.downloaded += bytes_amount
            now = time.time()
            
            # 每0.5秒更新一次显示
            if now - self.last_print_time < 0.5:
                return
            
            elapsed = now - self.start_time
            if elapsed > 0:
                # 计算瞬时速度（最近一段时间的速度）
                time_delta = now - self.last_print_time if self.last_print_time > 0 else elapsed
                bytes_delta = self.downloaded - self.last_downloaded
                speed = bytes_delta / time_delta if time_delta > 0 else 0
                
                # 计算进度百分比
                percent = min(self.downloaded / self.total_size * 100, 100.0)
                
                # 预估剩余时间
                if speed > 0:
                    remaining = (self.total_size - self.downloaded) / speed
                    eta = f"{int(remaining)}s"
                else:
                    eta = "..."
                
                # 打印进度（\r 覆盖当前行）
                print(f"\r  进度: {percent:5.1f}% | {human(self.downloaded)}/{human(self.total_size)} | "
                      f"速度: {human(int(speed))}/s | 剩余: {eta}    ", end="", flush=True)
            
            self.last_print_time = now
            self.last_downloaded = self.downloaded
    
    def finish(self):
        """下载完成，打印最终统计"""
        elapsed = time.time() - self.start_time
        avg_speed = self.downloaded / elapsed if elapsed > 0 else 0
        print(f"\r  完成: {human(self.total_size)} | 平均速度: {human(int(avg_speed))}/s | 耗时: {elapsed:.1f}s    ")

class FolderProgressTracker:
    """
    文件夹级别的下载进度跟踪器
    只统计最外层文件夹，动态更新进度
    """
    
    def __init__(self, csv_path: str, folder_depth: int = 1):
        """
        Args:
            csv_path: CSV 文件路径
            folder_depth: 统计的文件夹深度（1=最外层，2=第二层）
        """
        self.csv_path = csv_path
        self.folder_depth = folder_depth
        
        # 文件夹统计：{folder_path: {total_files, total_size, downloaded_files, downloaded_size}}
        self.folders: Dict[str, dict] = defaultdict(lambda: {
            'total_files': 0,
            'total_size': 0,
            'downloaded_files': 0,
            'downloaded_size': 0,
            'last_update': time.time()
        })
        
        self._last_write_time = 0
        self._write_interval = 10  # 每10秒写入一次
        self._lock = threading.Lock()
    
    def get_folder_key(self, file_path: str, prefix: str = "") -> str:
        """
        从文件路径提取文件夹路径
        
        例如：
        prefix="sar-data/tasks", file_path="sar-data/tasks/2024/01/file.tif"
        depth=1 -> "2024"
        depth=2 -> "2024/01"
        """
        # 移除 prefix
        if prefix and file_path.startswith(prefix):
            rel_path = file_path[len(prefix):].lstrip('/')
        else:
            rel_path = file_path
        
        # 提取文件夹
        parts = rel_path.split('/')
        if len(parts) <= 1:
            return rel_path  # 文件在根目录
        
        # 根据深度提取文件夹
        folder_parts = parts[:min(self.folder_depth, len(parts) - 1)]
        return '/'.join(folder_parts)
    
    def add_file(self, file_path: str, size: int, prefix: str = "", status: str = 'pending'):
        """
        添加文件到统计
        
        Args:
            file_path: 文件路径（S3 key）
            size: 文件大小
            prefix: S3 prefix（用于计算相对路径）
            status: 'pending', 'downloaded', 'already_present'
        """
        folder = self.get_folder_key(file_path, prefix)
        if not folder:
            return
        
        with self._lock:
            self.folders[folder]['total_files'] += 1
            self.folders[folder]['total_size'] += size
            
            if status in ['downloaded', 'already_present']:
                self.folders[folder]['downloaded_files'] += 1
                self.folders[folder]['downloaded_size'] += size
            
            self.folders[folder]['last_update'] = time.time()
    
    def mark_downloaded(self, file_path: str, size: int, prefix: str = ""):
        """
        标记文件为已下载
        """
        folder = self.get_folder_key(file_path, prefix)
        if not folder:
            return
        
        with self._lock:
            self.folders[folder]['downloaded_files'] += 1
            self.folders[folder]['downloaded_size'] += size
            self.folders[folder]['last_update'] = time.time()
        
        # 定期写入 CSV
        if time.time() - self._last_write_time > self._write_interval:
            self.write_csv()
    
    def get_progress(self, folder: str) -> str:
        """
        获取文件夹进度字符串
        
        Returns:
            "已完成" 或 "下载中 32%" 或 "等待中"
        """
        if folder not in self.folders:
            return "未知"
        
        data = self.folders[folder]
        total = data['total_files']
        downloaded = data['downloaded_files']
        
        if downloaded == 0:
            return "等待中"
        elif downloaded >= total:
            return "已完成"
        else:
            progress = int(downloaded / total * 100)
            return f"下载中 {progress}%"
    
    def write_csv(self, force: bool = False):
        """
        写入 CSV 文件
        
        Args:
            force: 强制写入（忽略时间间隔）
        """
        if not force and time.time() - self._last_write_time < self._write_interval:
            return
        
        if not self.csv_path:
            return
        
        with self._lock:
            try:
                with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                    # 获取文件锁
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except (IOError, OSError):
                        return  # 无法获取锁，跳过本次写入
                    
                    writer = csv.writer(f)
                    
                    # 写入表头
                    writer.writerow([
                        'folder_path',
                        'total_files',
                        'total_size_bytes',
                        'total_size_human',
                        'downloaded_files',
                        'downloaded_size_bytes',
                        'downloaded_size_human',
                        'progress',
                        'last_update'
                    ])
                    
                    # 写入数据（按文件夹路径排序）
                    for folder in sorted(self.folders.keys()):
                        data = self.folders[folder]
                        
                        total_size = data['total_size']
                        downloaded_size = data['downloaded_size']
                        progress = self.get_progress(folder)
                        
                        writer.writerow([
                            folder,
                            data['total_files'],
                            total_size,
                            human(total_size),
                            data['downloaded_files'],
                            downloaded_size,
                            human(downloaded_size),
                            progress,
                            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data['last_update']))
                        ])
                    
                    f.flush()
                    os.fsync(f.fileno())
                
                self._last_write_time = time.time()
            
            except IOError as e:
                pass  # 静默失败，不影响下载
    
    def get_summary(self) -> dict:
        """获取总体统计"""
        with self._lock:
            total_folders = len(self.folders)
            completed_folders = sum(1 for data in self.folders.values() 
                                   if data['downloaded_files'] >= data['total_files'])
            total_files = sum(data['total_files'] for data in self.folders.values())
            downloaded_files = sum(data['downloaded_files'] for data in self.folders.values())
            total_size = sum(data['total_size'] for data in self.folders.values())
            downloaded_size = sum(data['downloaded_size'] for data in self.folders.values())
            
            return {
                'total_folders': total_folders,
                'completed_folders': completed_folders,
                'pending_folders': total_folders - completed_folders,
                'total_files': total_files,
                'downloaded_files': downloaded_files,
                'total_size': total_size,
                'downloaded_size': downloaded_size,
                'overall_progress': int(downloaded_files / total_files * 100) if total_files > 0 else 0
            }
    
    def print_summary(self):
        """打印统计摘要"""
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print("文件夹下载进度统计")
        print("="*80)
        print(f"文件夹总数: {summary['total_folders']}")
        print(f"  已完成: {summary['completed_folders']}")
        print(f"  进行中: {summary['pending_folders']}")
        print(f"\n文件总数: {summary['total_files']}")
        print(f"  已下载: {summary['downloaded_files']}")
        print(f"  总进度: {summary['overall_progress']}%")
        print(f"\n总大小: {human(summary['total_size'])}")
        print(f"  已下载: {human(summary['downloaded_size'])}")
        print("="*80)

class CSVBatchWriter:
    """批量写入CSV，减少I/O，带备份机制和文件锁"""
    def __init__(self, path: str, batch_size: int = CSV_BATCH_SIZE):
        self.path = path
        self.batch_size = batch_size
        self.buffer = []
        self.backup_path = path + '.backup' if path else None
        self.write_failures = 0
        self._lock = threading.Lock()  # 线程锁
        self._last_flush_time = time.time()  # 上次刷新时间
    
    def write_header(self):
        if not self.path:
            return
        try:
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                # 获取文件锁（独占写锁）
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (IOError, OSError):
                    # 无法获取锁，可能被其他程序打开
                    print(f"警告: CSV文件被占用，跳过写入头")
                    return
                
                csv.writer(f).writerow([
                    "timestamp_iso", "bucket", "key", "size_bytes", "size_human",
                    "etag", "last_modified_iso", "local_path", "status"
                ])
                # 锁会在 with 块结束时自动释放
            self.write_failures = 0
        except IOError as e:
            print(f"警告: 无法写入CSV头 {self.path}: {e}")
    
    def append(self, row: list):
        if not self.path:
            return
        with self._lock:
            self.buffer.append(row)
            # 改进的刷新策略：
            # 1. buffer 达到批量大小
            # 2. 或者距离上次刷新超过 30 秒
            now = time.time()
            if len(self.buffer) >= self.batch_size or (now - self._last_flush_time) > 30:
                self.flush()
    
    def flush(self):
        if not self.path or not self.buffer:
            return
        
        with self._lock:
            # 先尝试写入主文件
            success = False
            try:
                with open(self.path, "a", newline="", encoding="utf-8") as f:
                    # 尝试获取文件锁（非阻塞）
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except (IOError, OSError):
                        # 无法获取锁，文件被占用（如 Excel 打开）
                        raise IOError("CSV文件被其他程序占用")
                    
                    w = csv.writer(f)
                    w.writerows(self.buffer)
                    # 强制刷新到磁盘
                    f.flush()
                    os.fsync(f.fileno())
                    # 锁会在 with 块结束时自动释放
                success = True
                self.write_failures = 0
                self._last_flush_time = time.time()
            except IOError as e:
                self.write_failures += 1
                # 只在第一次失败时打印警告，避免刷屏
                if self.write_failures == 1 or self.write_failures % 10 == 0:
                    print(f"警告: CSV写入失败 ({self.write_failures}次): {e}")
                
                # 如果连续失败，尝试写入备份文件
                if self.write_failures >= 3 and self.backup_path:
                    try:
                        with open(self.backup_path, "a", newline="", encoding="utf-8") as f:
                            try:
                                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                            except (IOError, OSError):
                                pass  # 备份文件不强制要求锁
                            w = csv.writer(f)
                            w.writerows(self.buffer)
                            f.flush()
                            os.fsync(f.fileno())
                        if self.write_failures == 3:  # 只在第一次使用备份时提示
                            print(f"已写入备份文件: {self.backup_path}")
                        success = True
                        self._last_flush_time = time.time()
                    except IOError:
                        if self.write_failures == 3:
                            print(f"警告: 备份文件写入也失败")
            
            # 只有成功写入才清空buffer
            if success:
                self.buffer.clear()
            elif len(self.buffer) > 1000:
                # 如果buffer过大（超过1000条），强制清空避免内存溢出
                print(f"警告: CSV buffer过大，强制清空 {len(self.buffer)} 条记录")
                self.buffer.clear()

def download_with_retry(s3, bucket: str, key: str, local: str, size: int) -> bool:
    """带断点续传、智能重试和进度显示的下载，成功返回True"""
    temp_local = local + ".tmp"
    show_progress = size >= PROGRESS_THRESHOLD
    support_resume = size >= RESUME_THRESHOLD
    
    network_retry_count = 0
    file_retry_count = 0
    
    while True:
        if _shutdown_requested:
            return False
        
        # 检查是否可以断点续传
        downloaded_size = 0
        if support_resume and os.path.exists(temp_local):
            downloaded_size = os.path.getsize(temp_local)
            if downloaded_size >= size:
                # 已下载完成，直接重命名
                try:
                    os.rename(temp_local, local)
                    return True
                except OSError as e:
                    print(f"  重命名失败: {e}")
                    downloaded_size = 0
            elif downloaded_size > 0:
                print(f"  检测到断点，从 {human(downloaded_size)} 继续下载")
        
        try:
            callback = None
            if show_progress:
                callback = ProgressCallback(size, os.path.basename(key), initial=downloaded_size)
            
            # 使用 Range 请求实现断点续传
            if downloaded_size > 0:
                extra_args = {'Range': f'bytes={downloaded_size}-'}
                with open(temp_local, 'ab') as f:
                    s3.download_fileobj(
                        Bucket=bucket,
                        Key=key,
                        Fileobj=f,
                        ExtraArgs=extra_args,
                        Callback=callback
                    )
            else:
                # 全新下载
                if callback:
                    s3.download_file(bucket, key, temp_local, Callback=callback)
                else:
                    s3.download_file(bucket, key, temp_local)
            
            # 下载成功，显示完成信息
            if show_progress and callback:
                callback.finish()
            
            # 验证文件大小
            if not os.path.exists(temp_local):
                raise OSError("临时文件不存在")
            temp_size = os.path.getsize(temp_local)
            if temp_size != size:
                raise OSError(f"文件大小不匹配: 期望 {size}, 实际 {temp_size}")
            
            # 重命名为最终文件
            os.rename(temp_local, local)
            return True
            
        except Exception as e:
            if show_progress:
                print()  # 换行
            
            is_network = is_network_error(e)
            
            if is_network:
                network_retry_count += 1
                # 计算退避时间
                delay_idx = min(network_retry_count - 1, len(RETRY_DELAYS) - 1)
                delay = RETRY_DELAYS[delay_idx]
                
                print(f"  网络错误 (第 {network_retry_count} 次): {type(e).__name__}")
                
                # 检查网络连接
                if not check_network_connectivity():
                    print(f"  网络不可达，{delay}秒后重试...")
                else:
                    print(f"  {delay}秒后重试...")
                
                # 可中断的等待
                for _ in range(delay):
                    if _shutdown_requested:
                        return False
                    time.sleep(1)
                
                # 网络错误不删除临时文件，保留断点
                continue
            else:
                # 文件错误（404、权限等）
                file_retry_count += 1
                print(f"  文件错误 (尝试 {file_retry_count}/{MAX_FILE_RETRIES}): {e}")
                
                if file_retry_count >= MAX_FILE_RETRIES:
                    print(f"  文件错误，已跳过")
                    # 清理临时文件
                    try:
                        if os.path.exists(temp_local):
                            os.remove(temp_local)
                    except OSError:
                        pass
                    return False
                
                time.sleep(5)
                # 文件错误删除临时文件重新下载
                try:
                    if os.path.exists(temp_local):
                        os.remove(temp_local)
                except OSError:
                    pass

def download_with_retry(s3, bucket: str, key: str, local: str, size: int, etag: Optional[str] = None) -> bool:
    """带断点续传、智能重试和进度显示的下载，成功返回True"""
    temp_local = local + ".tmp"
    show_progress = size >= PROGRESS_THRESHOLD
    support_resume = size >= RESUME_THRESHOLD
    
    network_retry_count = 0
    file_retry_count = 0
    retry_start_time = time.time()
    
    # 创建文件锁
    if not create_file_lock(temp_local):
        print(f"  文件被其他进程锁定，跳过")
        return False
    
    try:
        while True:
            if _shutdown_requested:
                return False
            
            # 检查全局重试时间上限
            if time.time() - retry_start_time > MAX_RETRY_TIME:
                print(f"  重试超时（{MAX_RETRY_TIME/3600:.1f}小时），已跳过")
                return False
            
            # 检查磁盘空间（需要2倍空间：临时文件+最终文件）
            if not check_disk_space(os.path.dirname(local) or '.', size * 2):
                print(f"  磁盘空间不足（需要 {human(size*2)} + {MIN_DISK_SPACE_GB}GB 缓冲）")
                time.sleep(60)  # 等待1分钟后重试
                continue
            
            # 检查是否可以断点续传
            downloaded_size = 0
            if support_resume and os.path.exists(temp_local):
                # 验证部分文件的完整性
                if verify_partial_file(temp_local, size, etag):
                    downloaded_size = os.path.getsize(temp_local)
                    if downloaded_size >= size:
                        # 已下载完成，直接重命名
                        if safe_rename(temp_local, local):
                            return True
                        else:
                            print(f"  重命名失败，重新下载")
                            downloaded_size = 0
                    elif downloaded_size > 0:
                        print(f"  检测到断点，从 {human(downloaded_size)} 继续下载")
                else:
                    # 部分文件损坏，删除重新下载
                    print(f"  临时文件校验失败，重新下载")
                    try:
                        os.remove(temp_local)
                        meta_file = temp_local + '.meta'
                        if os.path.exists(meta_file):
                            os.remove(meta_file)
                    except OSError:
                        pass
                    downloaded_size = 0
            
            try:
                callback = None
                if show_progress:
                    callback = ProgressCallback(size, os.path.basename(key), initial=downloaded_size)
                
                # 使用 Range 请求实现断点续传
                if downloaded_size > 0:
                    extra_args = {'Range': f'bytes={downloaded_size}-'}
                    with open(temp_local, 'ab') as f:
                        s3.download_fileobj(
                            Bucket=bucket,
                            Key=key,
                            Fileobj=f,
                            ExtraArgs=extra_args,
                            Callback=callback
                        )
                else:
                    # 全新下载
                    if callback:
                        s3.download_file(bucket, key, temp_local, Callback=callback)
                    else:
                        s3.download_file(bucket, key, temp_local)
                
                # 下载成功，显示完成信息
                if show_progress and callback:
                    callback.finish()
                
                # 验证文件大小
                if not os.path.exists(temp_local):
                    raise OSError("临时文件不存在")
                temp_size = os.path.getsize(temp_local)
                if temp_size != size:
                    raise OSError(f"文件大小不匹配: 期望 {size}, 实际 {temp_size}")
                
                # 保存元数据
                save_download_meta(temp_local, etag or '', size, temp_size)
                
                # 重命名为最终文件
                if safe_rename(temp_local, local):
                    # 清理元数据文件
                    try:
                        meta_file = temp_local + '.meta'
                        if os.path.exists(meta_file):
                            os.remove(meta_file)
                    except OSError:
                        pass
                    return True
                else:
                    raise OSError("文件重命名失败")
                
            except Exception as e:
                if show_progress:
                    print()  # 换行
                
                is_network = is_network_error(e)
                
                if is_network:
                    network_retry_count += 1
                    # 计算退避时间
                    delay_idx = min(network_retry_count - 1, len(RETRY_DELAYS) - 1)
                    delay = RETRY_DELAYS[delay_idx]
                    
                    # 过滤敏感信息
                    error_type = type(e).__name__
                    print(f"  网络错误 (第 {network_retry_count} 次): {error_type}")
                    
                    # 检查网络连接
                    if not check_network_connectivity():
                        print(f"  网络不可达，{delay}秒后重试...")
                    else:
                        print(f"  {delay}秒后重试...")
                    
                    # 保存当前进度元数据
                    if os.path.exists(temp_local):
                        current_size = os.path.getsize(temp_local)
                        save_download_meta(temp_local, etag or '', size, current_size)
                    
                    # 可中断的等待
                    for _ in range(delay):
                        if _shutdown_requested:
                            return False
                        time.sleep(1)
                    
                    # 网络错误不删除临时文件，保留断点
                    continue
                else:
                    # 文件错误（404、权限等）
                    file_retry_count += 1
                    # 过滤敏感信息
                    error_msg = str(e)
                    if len(error_msg) > 100:
                        error_msg = error_msg[:100] + '...'
                    print(f"  文件错误 (尝试 {file_retry_count}/{MAX_FILE_RETRIES}): {error_msg}")
                    
                    if file_retry_count >= MAX_FILE_RETRIES:
                        print(f"  文件错误，已跳过")
                        # 清理临时文件
                        try:
                            if os.path.exists(temp_local):
                                os.remove(temp_local)
                            meta_file = temp_local + '.meta'
                            if os.path.exists(meta_file):
                                os.remove(meta_file)
                        except OSError:
                            pass
                        return False
                    
                    time.sleep(5)
                    # 文件错误删除临时文件重新下载
                    try:
                        if os.path.exists(temp_local):
                            os.remove(temp_local)
                        meta_file = temp_local + '.meta'
                        if os.path.exists(meta_file):
                            os.remove(meta_file)
                    except OSError:
                        pass
    finally:
        # 清理文件锁
        remove_file_lock(temp_local)

def validate_args(args) -> bool:
    """验证参数有效性"""
    if args.cap_gb <= 0:
        print("错误: --cap-gb 必须大于 0")
        return False
    if not args.bucket:
        print("错误: --bucket 不能为空")
        return False
    if not args.out:
        print("错误: --out 不能为空")
        return False
    # 路径遍历检查
    out_abs = os.path.abspath(args.out)
    if ".." in args.out:
        print(f"警告: 输出路径包含 '..'，已规范化为: {out_abs}")
    args.out = out_abs
    # 检查输出目录是否可写
    try:
        os.makedirs(args.out, exist_ok=True)
        test_file = os.path.join(args.out, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except OSError as e:
        print(f"错误: 输出目录不可写 {args.out}: {e}")
        return False
    return True

def main():
    global _csv_writer
    
    # 注册信号处理（包括 SIGHUP）
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # Windows 不支持 SIGHUP
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)
    
    ap = argparse.ArgumentParser("Download from S3 (optimized)")
    ap.add_argument("--bucket", default="umbra-open-data-catalog")
    ap.add_argument("--prefix", default="sar-data/tasks")
    ap.add_argument("--region", default="us-west-2")
    ap.add_argument("--out", default="/mnt/nas/hjl/Umbra/UMBRA/umbra-data/tasks")
    ap.add_argument("--cap-gb", type=float, default=100000.0)
    ap.add_argument("--exclude-ext", default="")
    ap.add_argument("--dryrun", action="store_true")
    ap.add_argument("--csv", help="CSV log path")
    ap.add_argument("--verbose", "-v", action="store_true", help="显示详细调试信息")
    ap.add_argument("--max-list", type=int, help="最多列举多少个对象（用于测试）")
    ap.add_argument("--skip-csv-during-scan", action="store_true", 
                    help="统计阶段跳过CSV写入（加快速度）")
    ap.add_argument("--folder-depth", type=int, default=1,
                    help="CSV统计的文件夹深度（1=最外层，2=第二层，默认1）")
    args = ap.parse_args()

    if not validate_args(args):
        sys.exit(1)

    exclude = tuple(e.strip().lower() for e in args.exclude_ext.split(",") if e.strip())
    cap_bytes = int(args.cap_gb * 1024**3)
    prefix_len = len(args.prefix) if args.prefix else 0

    try:
        s3 = boto3.client("s3", config=S3_CONFIG, region_name=args.region)
    except Exception as e:
        print(f"错误: 无法创建S3客户端: {e}")
        sys.exit(1)
    
    paginator = s3.get_paginator("list_objects_v2")
    
    try:
        pages = paginator.paginate(Bucket=args.bucket, Prefix=args.prefix)
    except (ClientError, BotoCoreError) as e:
        print(f"错误: 无法访问S3 bucket {args.bucket}: {e}")
        sys.exit(1)

    # 第一遍：统计（流式，不存大列表）
    total_to_dl, total_size, already_cnt = 0, 0, 0
    
    if args.dryrun:
        print("=== DRY RUN ===")
        shown = 0
        try:
            for page in pages:
                if _shutdown_requested:
                    break
                for obj in page.get("Contents") or []:
                    key, size = obj["Key"], obj["Size"]
                    if not key or key.endswith("/"):  # 跳过目录
                        continue
                    if key.lower().endswith(exclude):
                        continue
                    rel = key[prefix_len:].lstrip("/") if prefix_len else key
                    # 安全检查：防止路径遍历攻击
                    if ".." in rel or rel.startswith("/"):
                        continue
                    local = os.path.join(args.out, rel)
                    
                    # 如果本地已存在且大小一致，就不占配额，直接标记为 already_present
                    if os.path.exists(local) and os.path.getsize(local) == size:
                        already_cnt += 1
                        continue
                    if total_size + size <= cap_bytes:
                        total_size += size
                        total_to_dl += 1
                        if shown < 20:
                            print(f" - {key} -> {human(size)}")
                            shown += 1
        except (ClientError, BotoCoreError) as e:
            print(f"错误: 列举S3对象失败: {e}")
            sys.exit(1)
        print(f"将下载: {total_to_dl} 文件, {human(total_size)}（上限 {args.cap_gb} GB）")
        print(f"已存在跳过: {already_cnt}")
        if total_to_dl > 20:
            print(f"... 其余 {total_to_dl - 20} 个省略")
        return

    # 正式下载：先统计，再下载
    # 使用文件夹级别的进度跟踪器
    folder_tracker = FolderProgressTracker(args.csv, folder_depth=args.folder_depth) if args.csv else None
    _csv_writer = folder_tracker  # 保存引用用于信号处理（兼容旧代码）
    
    if args.csv and folder_tracker:
        print(f"使用文件夹级别统计（深度={args.folder_depth}）")

    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    downloaded_cnt, downloaded_size, failed_cnt = 0, 0, 0

    # 第一遍：统计需要下载的文件
    print("正在统计文件...")
    to_download = []  # (key, size, local, etag)
    already_present = []  # 已存在的文件（用于延迟写入CSV）
    try:
        for page in pages:
            if _shutdown_requested:
                break
            for obj in page.get("Contents") or []:
                if _shutdown_requested:
                    break
                key = obj["Key"]
                size = obj["Size"]
                etag = (obj.get("ETag") or "").strip('"')
                
                if not key or key.endswith("/"):
                    continue
                if key.lower().endswith(exclude):
                    continue

                rel = key[prefix_len:].lstrip("/") if prefix_len else key
                # 安全检查：防止路径遍历攻击
                if ".." in rel or rel.startswith("/"):
                    print(f"  跳过不安全路径: {key}")
                    continue
                local = os.path.join(args.out, rel)
                
                # 如果本地已存在且大小一致，就不占配额，直接标记为 already_present
                if os.path.exists(local) and os.path.getsize(local) == size:
                    already_cnt += 1
                    
                    # 添加到文件夹统计
                    if folder_tracker:
                        folder_tracker.add_file(key, size, args.prefix, status='already_present')
                    
                    continue

                if total_size + size > cap_bytes:
                    continue

                total_size += size
                total_to_dl += 1
                to_download.append((key, size, local, etag))
                
                # 添加到文件夹统计（待下载）
                if folder_tracker:
                    folder_tracker.add_file(key, size, args.prefix, status='pending')
                
    except (ClientError, BotoCoreError) as e:
        print(f"错误: 列举S3对象失败: {e}")
        if folder_tracker:
            folder_tracker.write_csv(force=True)
        sys.exit(1)

    print(f"将下载: {total_to_dl} 文件, {human(total_size)}（上限 {args.cap_gb} GB）")
    print(f"已存在跳过: {already_cnt}")
    
    # 写入初始统计
    if folder_tracker:
        folder_tracker.write_csv(force=True)
        folder_tracker.print_summary()
    
    # 清理历史临时文件
    print("正在清理历史临时文件...")
    cleaned = cleanup_temp_files(args.out)
    if cleaned > 0:
        print(f"已清理 {cleaned} 个历史临时文件")
    
    if _shutdown_requested:
        if folder_tracker:
            folder_tracker.write_csv(force=True)
        print("用户中断")
        return

    # 第二遍：下载
    for i, (key, size, local, etag) in enumerate(to_download):
        if _shutdown_requested:
            print("用户中断，停止下载")
            break

        try:
            ensure_dir(local)
        except OSError:
            failed_cnt += 1
            continue
            
        print(f"[{i+1}/{total_to_dl}] {key} ({human(size)})")
        
        if download_with_retry(s3, args.bucket, key, local, size, etag):
            downloaded_cnt += 1
            downloaded_size += size
            
            # 更新文件夹进度
            if folder_tracker:
                folder_tracker.mark_downloaded(key, size, args.prefix)
        else:
            failed_cnt += 1

    # 最终写入CSV
    if folder_tracker:
        folder_tracker.write_csv(force=True)
        folder_tracker.print_summary()
    
    print(f"\n完成: 下载 {downloaded_cnt} 文件 ({human(downloaded_size)}), "
          f"跳过 {already_cnt} 已存在, 失败 {failed_cnt}")

if __name__ == "__main__":
    main()
