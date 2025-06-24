# 🎵 Pixabay Music Downloader

Tool để download nhạc MP3 từ Pixabay với khả năng chọn range theo số thứ tự.

## 🚀 Cài đặt

1. **Clone/Download project:**
```bash
git clone <repo-url>
cd py-draft
```

2. **Tạo virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate     # Windows
```

3. **Cài đặt dependencies:**
```bash
pip install -r requirements.txt
```

## 📖 Cách sử dụng

### Chạy tool:
```bash
python a.py
```

### Quy trình sử dụng:

1. **Nhập URL Pixabay** (hoặc để trống để dùng URL mặc định)
2. **Xem danh sách nhạc** được parse từ trang
3. **Nhập range download:**
   - Từ số: (vd: 1)
   - Đến số: (vd: 10)
4. **Chọn thư mục lưu** (mặc định: `downloads`)
5. **Xác nhận** để bắt đầu download

### Ví dụ:
```
🎵 PIXABAY MUSIC DOWNLOADER
==================================================
Nhập URL Pixabay (Enter để dùng mặc định):
> 

🔄 TÙY CHỌN CRAWLING:
1. Chỉ crawl trang đầu tiên (nhanh)
2. Crawl nhiều trang (chậm hơn nhưng có nhiều nhạc hơn)
Chọn (1/2, Enter = 1): 2
Từ trang (Enter = 1): 2
Đến trang (Enter = 3): 5

🚀 Sẽ crawl từ trang 2 đến trang 5 (4 trang)...
📄 TRANG 2/5
✅ Trang 2: Thêm 20 tracks
📄 TRANG 3/5  
✅ Trang 3: Thêm 20 tracks
📄 TRANG 4/5
✅ Trang 4: Thêm 20 tracks
📄 TRANG 5/5
✅ Trang 5: Thêm 20 tracks

📊 TỔNG KẾT CRAWLING:
✅ Thành công: 4/4 trang
📄 Range: Trang 2-5
🎵 Tổng tracks: 80

================================================================================
🎵 DANH SÁCH NHẠC TÌM THẤY
================================================================================

  1. Beautiful Piano Music (Trang 1)
     URL: https://pixabay.com/vi/music/...

📄 --- TRANG 2 ---
 21. Another Piano Track (Trang 2)
     URL: https://pixabay.com/vi/music/...

📝 Nhập range để download (1-60):
Từ số: 1
Đến số: 5
Thư mục lưu (Enter = 'downloads'): 

⬇️  Đang download 1: Beautiful Piano Music
   🔍 Thử lấy URL thực cho: Beautiful Piano Music
   📄 Fetching detail page...
   ✅ Tìm thấy URL trong JS: https://cdn.pixabay.com/download/audio/...
✅ Hoàn thành: 001_Beautiful_Piano_Music.mp3 (2,414,132 bytes)
```

## ✨ Tính năng

- ✅ **Parse Pixabay music pages** - Tự động lấy danh sách nhạc
- ✅ **Multi-page crawling** - Crawl nhiều trang với pagination (pagi=2, pagi=3...)
- ✅ **Real URL extraction** - Lấy URLs thực từ JavaScript trong detail pages
- ✅ **Hiển thị danh sách** với số thứ tự và thông tin trang
- ✅ **Download theo range** - Chọn từ bài số X đến bài số Y
- ✅ **Custom thư mục lưu** - Tự chọn nơi lưu file
- ✅ **Tên file an toàn** - Tự động làm sạch tên file
- ✅ **Báo cáo tiến độ** - Hiển thị thống kê download
- ✅ **Error handling** - Xử lý lỗi gracefully
- ✅ **Rate limiting** - Tránh bị block bởi server
- ✅ **Smart fallback** - Nhiều phương pháp backup khi gặp lỗi

## 🔧 Cấu trúc code

- `PixabayMusicDownloader` class chính
- `parse_pixabay_page()` - Parse trang web
- `display_music_list()` - Hiển thị danh sách
- `download_music_range()` - Download theo range
- `main()` - Interface chính

## ⚠️ Lưu ý

1. **Tôn trọng bản quyền** - Chỉ download nhạc royalty-free từ Pixabay
2. **Rate limiting** - Tool có delay 1s giữa mỗi download
3. **Network errors** - Sẽ retry hoặc skip nếu có lỗi mạng
4. **Pixabay structure** - Có thể cần update parser nếu Pixabay thay đổi cấu trúc

## 🐛 Troubleshooting

### Không tìm thấy nhạc:
- Kiểm tra URL có đúng không
- Thử URL khác
- Pixabay có thể cần JavaScript (hiện tại tool chỉ parse HTML tĩnh)

### Download lỗi:
- Kiểm tra kết nối mạng
- URL có thể đã expire
- File có thể không phải MP3

### Parser không hoạt động:
- Pixabay có thể đã thay đổi cấu trúc HTML
- Cần update selector trong `parse_pixabay_page()`

## 📄 License

Tool này chỉ để mục đích học tập và sử dụng cá nhân. Vui lòng tôn trọng bản quyền của Pixabay và các nghệ sĩ. 