#!/usr/bin/env python3
"""LLM-Wiki 部署脚本 — sync wiki/ + llmwiki/ 到服务器并重启服务。

仅做增量上传，绝不删除服务器文件（防止清除用户通过 Web UI 上传的文档）。
"""

import paramiko
import os
import sys
import argparse

# ---- 服务器配置 ----
HOST = "121.4.89.177"
USER = "ubuntu"
PASS = "988977Meme**"
REMOTE_BASE = "/opt/llm-wiki"

# ---- 本地项目路径 ----
LOCAL = os.path.dirname(os.path.abspath(__file__))

# 服务器独有文件（Web UI 上传的文档等）— 受保护，绝不被删除
PROTECTED_REMOTE_DIRS = ["wiki/sources", "wiki/sources/company-docs"]


def sync_file(sftp, rel_path) -> bool:
    """Upload a single file if it exists locally."""
    local_path = os.path.join(LOCAL, rel_path)
    remote_path = f"{REMOTE_BASE}/{rel_path}".replace("\\", "/")
    if os.path.exists(local_path):
        sftp.put(local_path, remote_path)
        return True
    return False


def sync_dir(sftp, local_dir, remote_dir) -> int:
    """Upload local files to remote. Never deletes remote files."""
    uploaded = 0
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".venv", "node_modules")]
        rel = os.path.relpath(root, local_dir)
        remote_root = os.path.join(remote_dir, rel).replace("\\", "/")

        try:
            sftp.stat(remote_root)
        except FileNotFoundError:
            try:
                sftp.mkdir(remote_root)
            except Exception:
                pass

        for f in files:
            local_path = os.path.join(root, f)
            remote_path = f"{remote_root}/{f}".replace("\\", "/")
            try:
                sftp.put(local_path, remote_path)
                uploaded += 1
            except Exception as e:
                print(f"  [FAIL] {remote_path}: {e}")

        if len(files) > 0:
            print(f"  [OK] {rel}/ ({len(files)} files)")

    return uploaded


def list_remote_only(sftp, local_dir, remote_dir) -> list[str]:
    """List files on remote that don't exist locally (user-uploaded, protected)."""
    remote_only: list[str] = []
    try:
        def _walk_remote(path):
            for entry in sftp.listdir_attr(path):
                full = f"{path}/{entry.filename}"
                if entry.st_mode & 0o40000:
                    _walk_remote(full)
                else:
                    rel = os.path.relpath(full, remote_dir)
                    local_path = os.path.join(local_dir, rel)
                    if not os.path.exists(local_path):
                        remote_only.append(full)
        _walk_remote(remote_dir)
    except Exception:
        pass
    return remote_only


def pull_remote_only(sftp, remote_dir, local_dir) -> int:
    """Download server-only files to local (rescue mode)."""
    pulled = 0
    try:
        def _walk_and_pull(path):
            nonlocal pulled
            for entry in sftp.listdir_attr(path):
                full = f"{path}/{entry.filename}"
                if entry.st_mode & 0o40000:
                    _walk_and_pull(full)
                else:
                    rel = os.path.relpath(full, remote_dir)
                    local_path = os.path.join(local_dir, rel)
                    if not os.path.exists(local_path):
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        sftp.get(full, local_path)
                        print(f"  [PULL] {rel} ({entry.st_size} bytes)")
                        pulled += 1
        _walk_and_pull(remote_dir)
    except Exception as e:
        print(f"  [WARN] pull failed: {e}")
    return pulled


def main():
    parser = argparse.ArgumentParser(description="LLM-Wiki deploy to server")
    parser.add_argument("--dry-run", action="store_true", help="Connect but don't transfer")
    parser.add_argument("--no-restart", action="store_true", help="Skip service restart")
    parser.add_argument("--wiki-only", action="store_true", help="Only sync wiki/ (content)")
    parser.add_argument("--code-only", action="store_true", help="Only sync llmwiki/ (code)")
    parser.add_argument("--pull", action="store_true",
                        help="Download server-only files to local (rescue user-uploaded docs)")
    args = parser.parse_args()

    print(f"Deploying to {HOST}...")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    if args.dry_run:
        print("Dry run — connected OK, exiting.")
        ssh.close()
        return

    sftp = ssh.open_sftp()
    total = 0

    # Pull mode: rescue server-only files
    if args.pull:
        print("Pulling server-only files to local...")
        for d in PROTECTED_REMOTE_DIRS:
            remote_d = f"{REMOTE_BASE}/{d}"
            local_d = os.path.join(LOCAL, d)
            total += pull_remote_only(sftp, remote_d, local_d)
        print(f"{total} files pulled from server.")
        sftp.close()
        ssh.close()
        return

    # Individual root files
    for f in ["VERSION", "DEPLOY_LOG.md", "pyproject.toml"]:
        if sync_file(sftp, f):
            total += 1
    print(f"  [OK] root files ({total} files)")

    # Wiki content
    if not args.code_only:
        print("\nSyncing wiki/ ...")
        total += sync_dir(sftp, os.path.join(LOCAL, "wiki"),
                          f"{REMOTE_BASE}/wiki")

    # Python package
    if not args.wiki_only:
        print("\nSyncing llmwiki/ ...")
        total += sync_dir(sftp, os.path.join(LOCAL, "llmwiki"),
                          f"{REMOTE_BASE}/llmwiki")

    # Warn about server-only files (user uploads)
    print("\nChecking for server-only files...")
    found_any = False
    for d in PROTECTED_REMOTE_DIRS:
        remote_d = f"{REMOTE_BASE}/{d}"
        local_d = os.path.join(LOCAL, d)
        orphan = list_remote_only(sftp, local_d, remote_d)
        if orphan:
            found_any = True
            print(f"  [INFO] {len(orphan)} server-only file(s) in {d}/ (user uploads, protected):")
            for f in orphan[:10]:
                print(f"         {os.path.basename(f)}")
    if not found_any:
        print("  [OK] no server-only files")

    sftp.close()
    print(f"\n{total} files synced.")

    if not args.no_restart:
        print("Restarting service...")
        stdin, stdout, stderr = ssh.exec_command(
            "sudo systemctl restart llmwiki && sudo systemctl status llmwiki --no-pager"
        )
        stdout.channel.recv_exit_status()
        out = stdout.read().decode()
        for line in out.split("\n"):
            if "Active:" in line:
                print(f"  {line.strip()}")
                break
    else:
        print("Skip restart (--no-restart).")

    ssh.close()
    print("Deploy complete.")


if __name__ == "__main__":
    main()
