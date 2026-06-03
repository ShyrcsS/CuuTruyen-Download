# CuuTruyen Chapter Downloader

Script tải truyện từ CuuTruyen.net

## Tính năng

- Tải truyện từ CuuTruyen.net
- Hỗ trợ DRM decryption để xử lý ảnh bị xáo trộn

## Cách sử dụng

```bash
python download_chapter.py [URL hoặc ID Chapter]
```

### Ví dụ

```bash
# Tải chapter bằng URL
python download_chapter.py https://cuutruyen.net/chapters/12345

# Tải chapter bằng ID
python download_chapter.py 12345

# Tải toàn bộ truyện bằng URL
python download_chapter.py https://cuutruyen.net/mangas/678
```

## Yêu cầu

- Python 3.7+
- requests
- Pillow (PIL)

## Cài đặt

```bash
pip install requests pillow
```