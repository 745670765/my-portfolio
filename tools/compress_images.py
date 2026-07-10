#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Darin Portfolio 图片压缩工具 v195
============================================================

作用：
- 扫描 assets 文件夹里的 jpg / jpeg / png / webp
- 超过 1.5MB 的图片会压缩
- 保留原路径和原文件名，index.html 不用改
- 原图备份到 _original_large_images
- 即使个别图片没法刚好压到 1.5MB，也会替换成“能做到的最小版本”，不会只备份不处理

使用：
python3 tools/compress_images.py

如果缺 Pillow：
python3 -m pip install pillow
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Optional, Tuple

try:
    from PIL import Image, ImageOps
except ImportError:
    print("缺少 Pillow 图片库。请先运行：")
    print("python3 -m pip install pillow")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
BACKUP_DIR = ROOT / "_original_large_images"

TARGET_MB = 1.5
TARGET_BYTES = int(TARGET_MB * 1024 * 1024)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def file_size(path: Path) -> int:
    return path.stat().st_size


def mb(size: int) -> float:
    return size / 1024 / 1024


def iter_images() -> Iterable[Path]:
    for path in ASSETS_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
            yield path


def backup_original(path: Path) -> None:
    relative = path.relative_to(ROOT)
    backup_path = BACKUP_DIR / relative
    if not backup_path.exists():
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)


def resize_to_max_side(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest <= max_side:
        return img
    scale = max_side / longest
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return img.resize(new_size, Image.LANCZOS)


def resize_by_scale(img: Image.Image, scale: float) -> Image.Image:
    w, h = img.size
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def write_candidate(path: Path, data: bytes, best: Optional[Tuple[int, bytes]]) -> Tuple[int, bytes]:
    size = len(data)
    if best is None or size < best[0]:
        return (size, data)
    return best


def save_jpeg_bytes(img: Image.Image, quality: int) -> bytes:
    from io import BytesIO
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(
        buf,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    return buf.getvalue()


def save_webp_bytes(img: Image.Image, quality: int) -> bytes:
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()


def save_png_bytes(img: Image.Image) -> bytes:
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    return buf.getvalue()


def has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA") or ("transparency" in img.info)


def compress_jpeg(path: Path, img: Image.Image) -> Tuple[bool, str]:
    best: Optional[Tuple[int, bytes]] = None

    # 先限制超大尺寸，减少网页加载压力；不强制所有图都变小，只有超过 1.5MB 的才处理。
    working = ImageOps.exif_transpose(img)
    if max(working.size) > 3200:
        working = resize_to_max_side(working, 3200)

    # 质量压缩
    for q in [90, 86, 82, 78, 74, 70, 66, 62, 58, 54, 50, 46, 42, 38, 34, 30, 26]:
        data = save_jpeg_bytes(working, q)
        best = write_candidate(path, data, best)
        if len(data) <= TARGET_BYTES:
            path.write_bytes(data)
            return True, f"JPEG 质量 {q}"

    # 继续缩尺寸 + 压质量
    for max_side in [2800, 2400, 2200, 2000, 1800, 1600, 1400, 1200, 1000, 900, 800]:
        resized = resize_to_max_side(working, max_side)
        for q in [82, 74, 66, 58, 50, 42, 34, 28]:
            data = save_jpeg_bytes(resized, q)
            best = write_candidate(path, data, best)
            if len(data) <= TARGET_BYTES:
                path.write_bytes(data)
                return True, f"JPEG 长边 {max_side}px / 质量 {q}"

    # 到这里还没到 3MB，也写入目前最小版本
    if best:
        path.write_bytes(best[1])
        return best[0] <= TARGET_BYTES, "JPEG 已写入可达到的最小版本"

    return False, "JPEG 压缩失败"


def compress_webp(path: Path, img: Image.Image) -> Tuple[bool, str]:
    best: Optional[Tuple[int, bytes]] = None
    working = ImageOps.exif_transpose(img)
    if max(working.size) > 3200:
        working = resize_to_max_side(working, 3200)

    for q in [86, 80, 74, 68, 62, 56, 50, 44, 38, 32, 26]:
        data = save_webp_bytes(working, q)
        best = write_candidate(path, data, best)
        if len(data) <= TARGET_BYTES:
            path.write_bytes(data)
            return True, f"WEBP 质量 {q}"

    for max_side in [2800, 2400, 2200, 2000, 1800, 1600, 1400, 1200, 1000, 900, 800]:
        resized = resize_to_max_side(working, max_side)
        for q in [78, 68, 58, 48, 38, 30]:
            data = save_webp_bytes(resized, q)
            best = write_candidate(path, data, best)
            if len(data) <= TARGET_BYTES:
                path.write_bytes(data)
                return True, f"WEBP 长边 {max_side}px / 质量 {q}"

    if best:
        path.write_bytes(best[1])
        return best[0] <= TARGET_BYTES, "WEBP 已写入可达到的最小版本"

    return False, "WEBP 压缩失败"


def compress_png(path: Path, img: Image.Image) -> Tuple[bool, str]:
    best: Optional[Tuple[int, bytes]] = None
    working = ImageOps.exif_transpose(img)

    # PNG 先优化原尺寸
    try:
        data = save_png_bytes(working)
        best = write_candidate(path, data, best)
        if len(data) <= TARGET_BYTES:
            path.write_bytes(data)
            return True, "PNG 优化"
    except Exception:
        pass

    # 尝试调色板压缩，保留 PNG 格式
    try:
        if has_alpha(working):
            quantized = working.convert("RGBA").quantize(colors=256, method=Image.FASTOCTREE)
        else:
            quantized = working.convert("RGB").quantize(colors=256)
        data = save_png_bytes(quantized)
        best = write_candidate(path, data, best)
        if len(data) <= TARGET_BYTES:
            path.write_bytes(data)
            return True, "PNG 调色板压缩"
    except Exception:
        pass

    # 缩尺寸 + PNG 优化
    for max_side in [3200, 2800, 2400, 2200, 2000, 1800, 1600, 1400, 1200, 1000, 900, 800, 700, 600]:
        resized = resize_to_max_side(working, max_side)
        try:
            data = save_png_bytes(resized)
            best = write_candidate(path, data, best)
            if len(data) <= TARGET_BYTES:
                path.write_bytes(data)
                return True, f"PNG 长边 {max_side}px"
        except Exception:
            pass

        # 缩尺寸后再量化
        try:
            if has_alpha(resized):
                quantized = resized.convert("RGBA").quantize(colors=256, method=Image.FASTOCTREE)
            else:
                quantized = resized.convert("RGB").quantize(colors=256)
            data = save_png_bytes(quantized)
            best = write_candidate(path, data, best)
            if len(data) <= TARGET_BYTES:
                path.write_bytes(data)
                return True, f"PNG 长边 {max_side}px / 调色板"
        except Exception:
            pass

    if best:
        path.write_bytes(best[1])
        return best[0] <= TARGET_BYTES, "PNG 已写入可达到的最小版本"

    return False, "PNG 压缩失败"


def compress_one(path: Path) -> None:
    original_size = file_size(path)
    if original_size <= TARGET_BYTES:
        print(f"跳过：{path.relative_to(ROOT)}  {mb(original_size):.2f}MB")
        return

    print(f"压缩：{path.relative_to(ROOT)}  原始 {mb(original_size):.2f}MB")
    backup_original(path)

    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:
        print(f"  失败：无法打开图片：{exc}")
        return

    suffix = path.suffix.lower()

    try:
        if suffix in (".jpg", ".jpeg"):
            ok, method = compress_jpeg(path, img)
        elif suffix == ".webp":
            ok, method = compress_webp(path, img)
        elif suffix == ".png":
            ok, method = compress_png(path, img)
        else:
            print("  跳过：不支持格式")
            return
    except Exception as exc:
        print(f"  失败：压缩过程出错：{exc}")
        return

    new_size = file_size(path)

    if new_size < original_size:
        if new_size <= TARGET_BYTES:
            print(f"  完成：{mb(original_size):.2f}MB → {mb(new_size):.2f}MB / {method}")
        else:
            print(f"  已变小但仍超过 1.5MB：{mb(original_size):.2f}MB → {mb(new_size):.2f}MB / {method}")
            print("  建议：这张图尺寸或透明 PNG 信息较重，可手动转 JPG/WebP 或继续降低尺寸。")
    else:
        print(f"  未变小：仍为 {mb(new_size):.2f}MB")
        print("  建议：检查是否为特殊 PNG、损坏图片，或手动导出为 JPG/WebP。")


def main() -> None:
    if not ASSETS_DIR.exists():
        print("没有找到 assets 文件夹。请在项目根目录运行。")
        raise SystemExit(1)

    print(f"项目目录：{ROOT}")
    print(f"扫描目录：{ASSETS_DIR}")
    print(f"压缩目标：单张图片 ≤ {TARGET_MB}MB")
    print("-" * 56)

    count = 0
    large_count = 0

    for path in iter_images():
        count += 1
        if file_size(path) > TARGET_BYTES:
            large_count += 1
        compress_one(path)

    print("-" * 56)
    print(f"扫描图片：{count} 张")
    print(f"超过 {TARGET_MB}MB：{large_count} 张")
    print(f"原图备份目录：{BACKUP_DIR.relative_to(ROOT)}")
    print("完成。")


if __name__ == "__main__":
    main()
