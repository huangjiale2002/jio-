
import os, argparse, csv, datetime
import boto3
from botocore import UNSIGNED
from botocore.config import Config

def human(n: int) -> str:
    u = ["B","KB","MB","GB","TB"]; i=0; s=float(n)
    while s>=1024 and i<len(u)-1: s/=1024; i+=1
    return f"{s:.2f} {u[i]}"

def ensure_dir(p: str):
    os.makedirs(os.path.dirname(p), exist_ok=True)

def write_csv_header_if_needed(csv_path: str):
    if not csv_path: return
    need_header = (not os.path.exists(csv_path)) or (os.path.getsize(csv_path)==0)
    if need_header:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp_iso",
                "bucket",
                "key",
                "size_bytes",
                "size_human",
                "etag",
                "last_modified_iso",
                "local_path",
                "status"  # downloaded | already_present
            ])

def append_csv_row(csv_path: str, row: list):
    if not csv_path: return
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

def main():
    ap = argparse.ArgumentParser("Download from S3 with total-size cap, export CSV for downloaded files")
    ap.add_argument("--bucket", default="umbra-open-data-catalog")
    ap.add_argument("--prefix", default="sar-data/tasks")
    ap.add_argument("--region", default="us-west-2")
    ap.add_argument("--out", default=r"Z:\hjl\Umbra\UMBRA\umbra\umbra-data\tasks")
    ap.add_argument("--cap-gb", type=float, default=100000.0, help="max total GB to fetch this run")
    ap.add_argument("--exclude-ext", default="", help="comma sep, e.g. .json,.xml")
    ap.add_argument("--dryrun", action="store_true")
    ap.add_argument("--csv", help="CSV path to log downloaded/already_present files of THIS RUN")
    ap.add_argument("--append", action="store_true", help="append to CSV if exists (default overwrite)")
    args = ap.parse_args()

    exclude = tuple(e.strip().lower() for e in args.exclude_ext.split(",") if e.strip())
    cap_bytes = int(args.cap_gb * 1024**3)

    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED), region_name=args.region)
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=args.bucket, Prefix=args.prefix)

    total=0
    selected = []  # (key, size, etag, last_modified)

    # 选文件（累计到 cap 以内；跳过本地已存在且大小一致的文件，不占用配额）
    for page in pages:
        for obj in page.get("Contents", []) or []:
            key = obj["Key"]
            size = int(obj["Size"])
            etag = (obj.get("ETag") or "").strip('"')
            last_modified = obj.get("LastModified")  # datetime or None
 
            # 后缀过滤
            if key.lower().endswith(exclude):
                continue

            # 如果本地已存在且大小一致，就不占配额，直接标记为 already_present
            rel = key[len(args.prefix):].lstrip("/") if args.prefix else key
            local = os.path.join(args.out, rel)
            if os.path.exists(local) and os.path.getsize(local) == size:
                selected.append((key, size, etag, last_modified, local, "already_present"))
                continue

            # 需要下载的才累计配额
            if total + size <= cap_bytes:
                selected.append((key, size, etag, last_modified, local, "to_download"))
                total += size
            else:
                # 超出配额的跳过
                continue

    # 汇总与展示
    to_dl = [x for x in selected if x[5] == "to_download"]
    already = [x for x in selected if x[5] == "already_present"]
    print(f"将下载文件数: {len(to_dl)}, 预计总量: {human(sum(x[1] for x in to_dl))}（上限 {args.cap_gb} GB）")
    print(f"已存在且跳过: {len(already)}")
    if args.dryrun:
        # 只展示前 20 条
        for t in to_dl[:20]:
            print(" -", t[0], "->", human(t[1]))
        if len(to_dl) > 20:
            print(f"... 其余 {len(to_dl)-20} 个省略")
        return

    # CSV 头（覆盖/追加）
    if args.csv and not args.append and os.path.exists(args.csv):
        os.remove(args.csv)
    write_csv_header_if_needed(args.csv)

    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    # 先把 already_present 也记到 CSV（方便合并统计）
    for key, size, etag, lm, local, status in already:
        append_csv_row(args.csv, [
            now_iso, args.bucket, key, size, human(size),
            etag, (lm.isoformat() if hasattr(lm, "isoformat") else ""),
            os.path.abspath(local), "already_present"
        ])

    # 正式下载 & 记录 CSV
    for key, size, etag, lm, local, status in to_dl:
        ensure_dir(local)
        print("Downloading:", key, "->", local, f"({human(size)})")
        s3.download_file(args.bucket, key, local)
        append_csv_row(args.csv, [
            now_iso, args.bucket, key, size, human(size),
            etag, (lm.isoformat() if hasattr(lm, "isoformat") else ""),
            os.path.abspath(local), "downloaded"
        ])

if __name__ == "__main__":
    main()
