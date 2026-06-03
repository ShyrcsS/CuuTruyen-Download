# Shyrcs Cuti Vl
import argparse
import base64
import math
import os
import re
import sys
from io import BytesIO

import requests
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

DEFAULT_BASE_URL = "https://cuutruyen.net"
DEFAULT_CLIENT = "OfficialWebApp-20250805"


def parse_target(value):
    chapter_match = re.search(r"/chapters/(\d+)", value)
    if chapter_match:
        return "chapter", int(chapter_match.group(1))

    manga_match = re.search(r"/mangas/(\d+)", value)
    if manga_match:
        return "manga", int(manga_match.group(1))

    if value.isdigit():
        return "chapter", int(value)

    raise ValueError("Vui lòng cung cấp ID hoặc URL của chapter/truyện bạn muốn download")


def xor_bytes(data, key):
    key_len = len(key)
    return bytes(data[i] ^ key[i % key_len] for i in range(len(data)))


def decrypt_drm_data(drm_data):
    if not drm_data:
        return []

    compact = "".join(drm_data.split())
    raw = base64.b64decode(compact)
    key = str(round(math.pi * 10**15)).encode("utf-8")
    decoded = xor_bytes(raw, key).decode("utf-8")

    parts = decoded.split("|")
    if parts and parts[0].startswith("#v"):
        parts = parts[1:]

    result = []
    for part in parts:
        if not part:
            continue
        y_str, h_str = part.split("-")
        result.append((int(y_str), int(h_str)))

    return result


def unscramble_image(scrambled, parts):
    if not parts:
        return scrambled

    width, height = scrambled.size
    output = Image.new(scrambled.mode, (width, height))
    src_y = 0

    for dest_y, part_h in parts:
        crop = scrambled.crop((0, src_y, width, src_y + part_h))
        output.paste(crop, (0, dest_y))
        src_y += part_h

    return output


def resolve_image_url(base_url, page):
    image_url = page.get("image_url")
    if image_url:
        return image_url
    image_path = page.get("image_path")
    if image_path:
        return f"{base_url.rstrip('/')}{image_path}"
    return None


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def sanitize_folder_name(name, fallback):
    if not name:
        return fallback
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    safe = safe.strip(" .")
    return safe or fallback


def build_headers(client, referer=None):
    headers = {"Cuutruyen-Client": client}
    if referer:
        headers["Referer"] = referer
    return headers


def fetch_json(session, url, headers, timeout):
    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_manga(session, base_url, headers, manga_id, timeout):
    url = f"{base_url.rstrip('/')}/api/v2/mangas/{manga_id}"
    payload = fetch_json(session, url, headers, timeout)
    return payload.get("data")


def fetch_chapters(session, base_url, headers, manga_id, timeout):
    url = f"{base_url.rstrip('/')}/api/v2/mangas/{manga_id}/chapters"
    payload = fetch_json(session, url, headers, timeout)
    return payload.get("data") or []


def fetch_chapter(session, base_url, headers, chapter_id, timeout):
    url = f"{base_url.rstrip('/')}/api/v2/chapters/{chapter_id}"
    payload = fetch_json(session, url, headers, timeout)
    return payload.get("data")


def build_output_dir(manga_name, manga_id, chapter_id, chapter_number):
    manga_safe = sanitize_folder_name(manga_name, f"manga_{manga_id or chapter_id}")
    chapter_label = str(chapter_number).strip() if chapter_number not in (None, "") else str(chapter_id)
    chapter_safe = sanitize_folder_name(f"chap {chapter_label}", f"chap_{chapter_id}")
    return os.path.join("download", manga_safe, chapter_safe)


def download_chapter(session, base_url, headers, chapter_id, manga_name, timeout):
    chapter = fetch_chapter(session, base_url, headers, chapter_id, timeout)
    if not chapter:
        print(f"Lỗi: chapter {chapter_id} không tìm thấy", file=sys.stderr)
        return

    pages = chapter.get("pages") or []
    if not pages:
        print(f"Lỗi: chapter {chapter_id} không có trang nào", file=sys.stderr)
        return

    pages = sorted(pages, key=lambda item: item.get("order", 0))

    manga = chapter.get("manga") or {}
    manga_id = manga.get("id")
    manga_name = manga_name or manga.get("name")
    chapter_number = chapter.get("number")

    out_dir = build_output_dir(manga_name, manga_id, chapter_id, chapter_number)
    ensure_dir(out_dir)

    referer = base_url
    if manga_id:
        referer = f"{base_url.rstrip('/')}/mangas/{manga_id}/chapters/{chapter_id}"
    image_headers = build_headers(DEFAULT_CLIENT, referer)

    for index, page in enumerate(pages, start=1):
        image_url = resolve_image_url(base_url, page)
        if not image_url:
            print(f"Bỏ qua trang {index}: thiếu đường dẫn ảnh", file=sys.stderr)
            continue

        output_name = f"{index}.png"
        output_path = os.path.join(out_dir, output_name)

        img_resp = session.get(image_url, headers=image_headers, timeout=timeout)
        img_resp.raise_for_status()

        scrambled = Image.open(BytesIO(img_resp.content))
        scrambled.load()

        parts = decrypt_drm_data(page.get("drm_data"))
        restored = unscramble_image(scrambled, parts)

        restored.save(output_path, format="PNG")
        print(f"Đã lưu {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Tải xuống và giải mã ảnh từ CuuTruyen"
    )
    parser.add_argument("target", help="URL/ID chapter hoặc URL truyện")
    parser.add_argument("--timeout", type=int, default=60, help="Thời gian chờ HTTP tính bằng giây (để tránh lỗi timeout khi tải ảnh)")

    args = parser.parse_args()

    try:
        target_type, target_id = parse_target(args.target)
    except ValueError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2

    session = requests.Session()
    base_url = DEFAULT_BASE_URL
    headers = build_headers(DEFAULT_CLIENT, base_url)

    if target_type == "chapter":
        download_chapter(session, base_url, headers, target_id, None, args.timeout)
        return 0

    manga = fetch_manga(session, base_url, headers, target_id, args.timeout)
    if not manga:
        print(f"Lỗi: truyện {target_id} không tìm thấy", file=sys.stderr)
        return 2

    manga_name = manga.get("name")
    chapters = fetch_chapters(session, base_url, headers, target_id, args.timeout)
    if not chapters:
        print("Lỗi: không tìm thấy chapter nào cho truyện này", file=sys.stderr)
        return 2

    chapters = sorted(chapters, key=lambda item: item.get("order", 0))
    for chapter in chapters:
        chapter_id = chapter.get("id")
        if not chapter_id:
            continue
        download_chapter(session, base_url, headers, chapter_id, manga_name, args.timeout)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
