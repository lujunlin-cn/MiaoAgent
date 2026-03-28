"""
Download required pretrained models into /opt/catagent/models.

Usage:
  python3 models/download_pretrained_models.py
  python3 models/download_pretrained_models.py --only emotion2vec bge panns
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parent
EMOTION2VEC_DIR = ROOT / "emotion2vec_plus_large"
BGE_DIR = ROOT / "bge-large-zh-v1.5"
PANNS_DIR = ROOT / "panns"
PANNS_CKPT = PANNS_DIR / "Cnn14_mAP=0.431.pth"
URBAN_SOUND_DIR = ROOT / "urbansound8k_ecapa"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_emotion2vec() -> bool:
    print("[download] emotion2vec ->", EMOTION2VEC_DIR)
    try:
        from modelscope import snapshot_download

        _ensure_dir(EMOTION2VEC_DIR)
        snapshot_download(
            model_id="iic/emotion2vec_plus_large",
            local_dir=str(EMOTION2VEC_DIR),
            local_files_only=False,
        )
        ok = (EMOTION2VEC_DIR / "model.pt").exists()
        print("[download] emotion2vec", "ok" if ok else "failed")
        return ok
    except Exception as e:
        print(f"[download] emotion2vec failed: {e}")
        return False


def download_bge() -> bool:
    print("[download] bge-large-zh-v1.5 ->", BGE_DIR)
    try:
        from modelscope import snapshot_download

        _ensure_dir(BGE_DIR)
        snapshot_download(
            model_id="BAAI/bge-large-zh-v1.5",
            local_dir=str(BGE_DIR),
            local_files_only=False,
        )
        ok = (BGE_DIR / "pytorch_model.bin").exists()
        print("[download] bge", "ok" if ok else "failed")
        return ok
    except Exception as e:
        print(f"[download] bge failed: {e}")
        return False


def _run_download(url: str, out_path: Path) -> bool:
    cmd = [
        "curl",
        "-Lk",
        "--retry",
        "2",
        "--connect-timeout",
        "20",
        "-o",
        str(out_path),
        url,
    ]
    try:
        p = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if p.returncode != 0:
            return False
        return out_path.exists() and out_path.stat().st_size > 300 * 1024 * 1024
    except Exception:
        return False


def download_panns() -> bool:
    print("[download] panns ckpt ->", PANNS_CKPT)
    _ensure_dir(PANNS_DIR)

    # Try mirrors first, then legacy URL.
    urls: List[str] = [
        "https://hf-mirror.com/spaces/qiuqiangkong/panns_inference/resolve/main/Cnn14_mAP%3D0.431.pth",
        "https://hf-mirror.com/qiuqiangkong/panns_inference/resolve/main/Cnn14_mAP%3D0.431.pth",
        "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1",
    ]

    for url in urls:
        print("[download] try:", url)
        if _run_download(url, PANNS_CKPT):
            print("[download] panns ok")
            return True

    if PANNS_CKPT.exists() and PANNS_CKPT.stat().st_size < 300 * 1024 * 1024:
        try:
            PANNS_CKPT.unlink()
        except Exception:
            pass
    print("[download] panns failed (no reachable mirror)")
    return False


def download_urbansound() -> bool:
    print("[download] urbansound8k_ecapa ->", URBAN_SOUND_DIR)
    try:
        from modelscope import snapshot_download

        _ensure_dir(URBAN_SOUND_DIR)
        snapshot_download(
            model_id="speechbrain/urbansound8k_ecapa",
            local_dir=str(URBAN_SOUND_DIR),
            local_files_only=False,
        )
        ok = (URBAN_SOUND_DIR / "embedding_model.ckpt").exists()
        print("[download] urbansound", "ok" if ok else "failed")
        return ok
    except Exception as e:
        print(f"[download] urbansound failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Download pretrained models to local models directory")
    parser.add_argument(
        "--only",
        nargs="*",
        default=["emotion2vec", "bge", "urbansound", "panns"],
        choices=["emotion2vec", "bge", "urbansound", "panns"],
    )
    args = parser.parse_args()

    results = {}
    if "emotion2vec" in args.only:
        results["emotion2vec"] = download_emotion2vec()
    if "bge" in args.only:
        results["bge"] = download_bge()
    if "urbansound" in args.only:
        results["urbansound"] = download_urbansound()
    if "panns" in args.only:
        results["panns"] = download_panns()

    print("\n=== summary ===")
    for k, v in results.items():
        print(f"{k}: {'ok' if v else 'failed'}")


if __name__ == "__main__":
    main()
