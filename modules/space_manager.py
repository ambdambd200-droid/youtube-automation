"""
Space Manager — deletes source video files after they've been processed.
Keeps only the final Short clip and thumbnails.
"""
import json
import os
import sys
import shutil
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DOWNLOADS_DIR


def delete_file(filepath):
    """Safely delete a file, logging any errors."""
    if not filepath or not os.path.exists(filepath):
        return False
    try:
        os.remove(filepath)
        print(f"  [space] Deleted: {os.path.basename(filepath)} ({os.path.getsize(filepath)} bytes freed)", flush=True)
        return True
    except OSError as e:
        print(f"  [space] Error deleting {filepath}: {e}", flush=True)
        return False


def delete_directory(dirpath):
    """Safely delete a directory and all contents."""
    if not dirpath or not os.path.exists(dirpath):
        return False
    try:
        shutil.rmtree(dirpath)
        print(f"  [space] Deleted directory: {dirpath}", flush=True)
        return True
    except OSError as e:
        print(f"  [space] Error deleting directory {dirpath}: {e}", flush=True)
        return False


def cleanup_source(source_paths):
    """Delete raw downloaded source files after processing.

    Args:
        source_paths: List of file paths to delete (source downloads)
    """
    count = 0
    freed = 0
    for path in source_paths:
        if path and os.path.exists(path):
            try:
                size = os.path.getsize(path)
                os.remove(path)
                count += 1
                freed += size
            except OSError as e:
                print(f"  [space] Error: {e}", flush=True)

    if count > 0:
        print(f"  [space] Cleaned {count} source files ({freed / 1024 / 1024:.1f} MB freed)", flush=True)

    # Also clean any other files in downloads dir that are > 24 hours old
    cleanup_old_downloads()

    return count


def cleanup_old_downloads(max_age_hours=24):
    """Remove any leftover files in downloads dir older than max_age_hours."""
    if not os.path.exists(DOWNLOADS_DIR):
        return

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    count = 0
    freed = 0

    for fname in os.listdir(DOWNLOADS_DIR):
        fpath = os.path.join(DOWNLOADS_DIR, fname)
        if os.path.isfile(fpath):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    size = os.path.getsize(fpath)
                    os.remove(fpath)
                    count += 1
                    freed += size
            except OSError:
                pass

    if count > 0:
        print(f"  [space] Cleaned {count} old download files ({freed / 1024 / 1024:.1f} MB)", flush=True)


def cleanup_old_clips(max_days=7):
    """Remove processed clips older than max_days (keeps space from accumulating)."""
    from config import CLIPS_DIR
    if not os.path.exists(CLIPS_DIR):
        return

    cutoff = datetime.now() - timedelta(days=max_days)
    count = 0
    freed = 0

    for fname in os.listdir(CLIPS_DIR):
        fpath = os.path.join(CLIPS_DIR, fname)
        if os.path.isfile(fpath) and fname.endswith(".mp4"):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    size = os.path.getsize(fpath)
                    os.remove(fpath)
                    count += 1
                    freed += size
            except OSError:
                pass

    if count > 0:
        print(f"  [space] Cleaned {count} old processed clips ({freed / 1024 / 1024:.1f} MB)", flush=True)


def log_space_usage():
    """Log current disk space usage for the assets directory."""
    from config import OUTPUT_DIR
    total_size = 0
    file_count = 0

    for root, dirs, files in os.walk(OUTPUT_DIR):
        for f in files:
            fpath = os.path.join(root, f)
            try:
                total_size += os.path.getsize(fpath)
                file_count += 1
            except OSError:
                pass

    print(f"  [space] Assets: {file_count} files, {total_size / 1024 / 1024:.1f} MB total", flush=True)
    return {"files": file_count, "size_mb": total_size / 1024 / 1024}


def full_cleanup(source_paths):
    """Run full cleanup cycle after a successful upload."""
    print(f"\n>>> Running space cleanup...", flush=True)

    # 1. Delete source downloads
    cleanup_source(source_paths)

    # 2. Remove old clips (older than 7 days)
    cleanup_old_clips(max_days=7)

    # 3. Log current usage
    usage = log_space_usage()

    return usage


if __name__ == "__main__":
    # Test
    usage = full_cleanup([])
    print(json.dumps(usage, indent=2))
