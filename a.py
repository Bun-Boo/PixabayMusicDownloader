#!/usr/bin/env python3
"""
Pixabay Music Downloader Tool
Tải nhạc MP3 từ Pixabay với khả năng chọn range
"""

import requests
from bs4 import BeautifulSoup
import re
import os
import urllib.parse
from urllib.parse import urljoin
import time
import json
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from threading import Lock

class PixabayMusicDownloader:
    def __init__(self):
        self.session = requests.Session()
        # Headers mạnh hơn để giả lập browser thật
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        self.music_list = []
        # Threading locks for thread-safe operations
        self.print_lock = Lock()
        self.progress_lock = Lock()
        
    def parse_pixabay_page(self, url: str) -> List[Dict]:
        """
        Parse trang Pixabay để lấy danh sách nhạc
        """
        print(f"🔍 Đang tải trang: {url}")
        
        try:
            # Thử với delay và timeout để tránh bị block
            time.sleep(2)
            response = self.session.get(url, timeout=30, allow_redirects=True)
            
            print(f"📊 Status code: {response.status_code}")
            print(f"📊 Content length: {len(response.content):,} bytes")
            
            if response.status_code == 403:
                print("⚠️  403 Forbidden - Thử phương pháp khác...")
                return self._try_alternative_methods(url)
            
            response.raise_for_status()
            
            music_items = self._parse_response_content(response.content, url)
            self.music_list = music_items
            return music_items
            
        except Exception as e:
            print(f"❌ Lỗi khi tải trang: {e}")
            print("💡 Thử phương pháp thay thế...")
            return self._try_alternative_methods(url)
    
    def _parse_single_page(self, page_url: str, page_num: int) -> Dict:
        """
        Parse một trang đơn lẻ - dùng cho threading
        Returns: Dict với thông tin kết quả parse
        """
        result = {
            'page_num': page_num,
            'success': False,
            'items': [],
            'error': None,
            'url': page_url
        }
        
        try:
            with self.print_lock:
                print(f"📄 [{threading.current_thread().name}] Đang crawl trang {page_num}: {page_url}")
            
            # Parse trang hiện tại
            page_items = self.parse_pixabay_page(page_url)
            
            if page_items:
                # Thêm page number vào từng item
                for item in page_items:
                    item['page'] = page_num
                
                result['items'] = page_items
                result['success'] = True
                
                with self.print_lock:
                    print(f"✅ [{threading.current_thread().name}] Trang {page_num}: Thêm {len(page_items)} tracks")
            else:
                result['error'] = "Không tìm thấy tracks"
                with self.print_lock:
                    print(f"❌ [{threading.current_thread().name}] Trang {page_num}: Không tìm thấy tracks")
                    
        except Exception as e:
            result['error'] = str(e)
            with self.print_lock:
                print(f"❌ [{threading.current_thread().name}] Lỗi khi crawl trang {page_num}: {e}")
        
        return result

    def parse_multiple_pages(self, base_url: str, start_page: int = 1, end_page: int = 3, max_workers: int = 3) -> List[Dict]:
        """
        Parse nhiều trang Pixabay với pagination từ start_page đến end_page sử dụng multi-threading
        max_workers: Số thread tối đa cho parsing (mặc định 3 để không làm quá tải server)
        """
        all_music_items = []
        total_pages = end_page - start_page + 1
        
        print(f"📚 Bắt đầu crawl từ trang {start_page} đến trang {end_page} ({total_pages} trang)...")
        print(f"🧵 Sử dụng {max_workers} threads song song cho parsing")
        print("=" * 70)
        
        # Chuẩn bị danh sách parse jobs
        parse_jobs = []
        for page_num in range(start_page, end_page + 1):
            # Tạo URL cho từng trang
            if page_num == 1 and 'pagi=' not in base_url:
                page_url = base_url
            else:
                # Thêm parameter pagi cho trang tiếp theo
                separator = '&' if '?' in base_url else '?'
                if 'pagi=' in base_url:
                    # Replace existing pagi parameter
                    page_url = re.sub(r'pagi=\d+', f'pagi={page_num}', base_url)
                else:
                    page_url = f"{base_url}{separator}pagi={page_num}"
            
            parse_jobs.append((page_url, page_num))
        
        print(f"📋 Đã chuẩn bị {len(parse_jobs)} jobs parsing...")
        
        # Khởi tạo counters
        successful_pages = 0
        failed_pages = 0
        completed_pages = 0
        
        # Sử dụng ThreadPoolExecutor để parse song song
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Parser") as executor:
            # Submit tất cả jobs
            future_to_job = {
                executor.submit(self._parse_single_page, page_url, page_num): (page_url, page_num) 
                for page_url, page_num in parse_jobs
            }
            
            print(f"🎯 Đã submit {len(future_to_job)} parse tasks...")
            print("⏳ Đang crawl... (có thể mất vài phút)")
            print("-" * 70)
            
            # Thu thập kết quả theo thứ tự hoàn thành
            page_results = {}
            
            for future in as_completed(future_to_job):
                page_url, page_num = future_to_job[future]
                completed_pages += 1
                
                try:
                    result = future.result()
                    page_results[page_num] = result
                    
                    with self.progress_lock:
                        if result['success']:
                            successful_pages += 1
                        else:
                            failed_pages += 1
                        
                        # Hiển thị tiến độ
                        progress = (completed_pages / len(parse_jobs)) * 100
                        print(f"\n📊 Tiến độ parsing: {completed_pages}/{len(parse_jobs)} ({progress:.1f}%)")
                        print(f"✅ Thành công: {successful_pages} | ❌ Thất bại: {failed_pages}")
                        
                except Exception as e:
                    with self.print_lock:
                        print(f"❌ Lỗi unexpected khi xử lý trang {page_num}: {e}")
                    failed_pages += 1
        
        # Sắp xếp và ghép kết quả theo thứ tự trang
        print(f"\n🔗 Đang ghép kết quả từ {len(page_results)} trang...")
        
        current_index = 1
        for page_num in sorted(page_results.keys()):
            result = page_results[page_num]
            if result['success'] and result['items']:
                # Update index để không trùng lặp
                for item in result['items']:
                    item['index'] = current_index
                    current_index += 1
                
                all_music_items.extend(result['items'])
                print(f"📄 Trang {page_num}: Đã thêm {len(result['items'])} tracks")
        
        print(f"\n📊 TỔNG KẾT CRAWLING:")
        print(f"✅ Thành công: {successful_pages}/{total_pages} trang")
        print(f"❌ Thất bại: {failed_pages}/{total_pages} trang")
        print(f"📊 Tỷ lệ thành công: {(successful_pages/total_pages*100):.1f}%")
        print(f"📄 Range: Trang {start_page}-{end_page}")
        print(f"🎵 Tổng tracks: {len(all_music_items)}")
        print("=" * 70)
        
        self.music_list = all_music_items
        return all_music_items
    
    def _try_alternative_methods(self, url: str) -> List[Dict]:
        """
        Thử các phương pháp thay thế khi gặp lỗi 403 hoặc blocked
        """
        print("🔄 Đang thử các phương pháp thay thế...")
        
        # Method 1: Thử với session mới và headers khác
        try:
            print("📋 Phương pháp 1: Session mới + headers khác...")
            new_session = requests.Session()
            new_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://pixabay.com/',
                'Origin': 'https://pixabay.com'
            })
            
            time.sleep(3)
            response = new_session.get(url, timeout=30)
            if response.status_code == 200:
                print("✅ Thành công với phương pháp 1!")
                return self._parse_response_content(response.content, url)
                
        except Exception as e:
            print(f"❌ Phương pháp 1 thất bại: {e}")
        
        # Method 2: Thử URL đơn giản hơn 
        try:
            print("📋 Phương pháp 2: URL đơn giản...")
            simple_url = "https://pixabay.com/music/search/piano/"
            response = self.session.get(simple_url, timeout=30)
            if response.status_code == 200:
                print("✅ Thành công với URL đơn giản!")
                return self._parse_response_content(response.content, simple_url)
                
        except Exception as e:
            print(f"❌ Phương pháp 2 thất bại: {e}")
        
        # Method 3: Gợi ý sử dụng URL trực tiếp
        print("📋 Phương pháp 3: Hướng dẫn lấy URL trực tiếp...")
        print("""
💡 GỢI Ý: Pixabay có thể cần truy cập trực tiếp qua browser.
Hãy thử:
1. Mở {url} trong browser
2. Mở Developer Tools (F12)
3. Tìm các file .mp3 trong Network tab
4. Copy URL trực tiếp của file MP3

Hoặc nhập URL khác để thử:""".format(url=url))
        
        return self._create_demo_list()
    
    def _parse_response_content(self, content: bytes, url: str) -> List[Dict]:
        """
        Parse nội dung response thành danh sách nhạc
        """
        soup = BeautifulSoup(content, 'html.parser')
        music_items = []
        
        # Debug: Tìm hiểu cấu trúc HTML thực tế
        print("🔍 Đang phân tích cấu trúc HTML...")
        
        # Tìm các patterns cụ thể của Pixabay (dựa trên HTML thực)
        patterns_to_try = [
            ('div[class*="audioRow"]', 'Pixabay audioRow containers'),
            ('div[class*="Row"]', 'Pixabay Row containers'),
            ('div[class*="item"]', 'div có class chứa "item"'),
            ('div[class*="media"]', 'div có class chứa "media"'),
            ('div[class*="result"]', 'div có class chứa "result"'),
            ('div[class*="track"]', 'div có class chứa "track"'),
            ('div[class*="audio"]', 'div có class chứa "audio"'),
            ('div[class*="music"]', 'div có class chứa "music"'),
            ('article', 'article elements'),
            ('div[data-id]', 'div có data-id'),
            ('.item', 'class item'),
            ('.media', 'class media'),
            ('.track', 'class track'),
            ('[data-track]', 'elements có data-track'),
            ('[data-audio]', 'elements có data-audio'),
        ]
        
        items = []
        for selector, description in patterns_to_try:
            try:
                found_items = soup.select(selector)
                if found_items:
                    print(f"✅ Tìm thấy {len(found_items)} items với selector: {description}")
                    items = found_items
                    break
                else:
                    print(f"❌ Không tìm thấy với selector: {description}")
            except Exception as e:
                print(f"⚠️  Lỗi với selector {description}: {e}")
        
        if not items:
            # Fallback: tìm tất cả divs và filter
            print("🔄 Thử fallback method...")
            all_divs = soup.find_all('div')
            print(f"📊 Tổng số div tags: {len(all_divs)}")
            
            # Tìm divs có thể chứa thông tin nhạc
            for div in all_divs[:50]:  # Chỉ check 50 divs đầu
                if any(keyword in str(div.get('class', [])).lower() for keyword in ['item', 'media', 'track', 'music', 'audio', 'result']):
                    items.append(div)
                elif any(attr.startswith('data-') for attr in div.attrs if 'id' in attr or 'track' in attr or 'audio' in attr):
                    items.append(div)
        
        print(f"📋 Cuối cùng tìm thấy {len(items)} items để parse")
        
        for idx, item in enumerate(items):
            try:
                print(f"\n🔍 Đang parse item {idx + 1}...")
                
                # Debug: In ra thông tin cơ bản của item
                item_classes = item.get('class', [])
                item_id = item.get('id', '')
                print(f"   Classes: {item_classes}")
                print(f"   ID: {item_id}")
                
                # Tìm title theo cấu trúc Pixabay cụ thể
                title = "Unknown Track"
                
                # Pixabay có class title--xxxxx trong structure
                title_selectors = [
                    'a[class*="title"]',  # a.title--7N7Nr
                    '[class*="title"]',   # Các element khác có title
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    '[title]', '[alt]', 
                    '.nameAndTitle a:first-child',  # Link đầu tiên trong nameAndTitle
                    'a[href*="/music/"]',  # Links đến trang music
                    'span', 'div', 'p'
                ]
                
                for selector in title_selectors:
                    title_elem = item.select_one(selector)
                    if title_elem:
                        candidate_title = title_elem.get_text(strip=True) or title_elem.get('title', '') or title_elem.get('alt', '')
                        if candidate_title and len(candidate_title) > 2 and candidate_title != 'Unknown Track':
                            title = candidate_title
                            print(f"   ✅ Tìm thấy title với selector '{selector}': {title}")
                            break
                
                # Tìm download link - Pixabay sử dụng JavaScript cho download
                download_link = None
                
                # 1. Tìm URL trang chi tiết (để có thể fetch sau)
                detail_link = None
                detail_links = item.find_all('a', href=True)
                for link in detail_links:
                    href = link.get('href', '')
                    if '/music/' in href and any(word in href for word in ['/', '-']):
                        detail_link = urljoin(url, href)
                        print(f"   ✅ Tìm thấy detail page: {detail_link}")
                        break
                
                # 2. Tìm audio elements (ít khả năng có)
                audio_elem = item.find('audio')
                if audio_elem and audio_elem.get('src'):
                    download_link = urljoin(url, audio_elem['src'])
                    print(f"   ✅ Tìm thấy audio src: {download_link}")
                
                # 3. Tìm data attributes có thể chứa track ID
                track_id = None
                if not download_link:
                    for attr, value in item.attrs.items():
                        if 'data' in attr.lower() and ('id' in attr.lower() or 'track' in attr.lower()):
                            track_id = str(value)
                            print(f"   ✅ Tìm thấy track ID: {track_id}")
                            break
                
                # 4. Extract ID từ detail link nếu có
                if not track_id and detail_link:
                    # Pixabay URLs thường có format: /music/title-123456/
                    id_match = re.search(r'-(\d+)/?$', detail_link)
                    if id_match:
                        track_id = id_match.group(1)
                        print(f"   ✅ Extract track ID từ URL: {track_id}")
                
                # 5. Ưu tiên dùng detail page để fetch URL thực
                if detail_link:
                    download_link = detail_link
                    print(f"   🔗 Sẽ fetch URL thực từ detail page: {detail_link}")
                elif track_id:
                    # Backup: thử các format khả dĩ
                    possible_formats = [
                        f"https://cdn.pixabay.com/audio/2023/{track_id}.mp3",
                        f"https://cdn.pixabay.com/audio/2024/{track_id}.mp3", 
                        f"https://pixabay.com/get/{track_id}.mp3",
                        f"https://pixabay.com/music/download/{track_id}.mp3"
                    ]
                    download_link = possible_formats[0]
                    print(f"   🔗 Tạo download link giả định: {download_link}")
                
                # 6. Tìm trong child elements nếu vẫn chưa có
                if not download_link:
                    for child in item.find_all(recursive=True):
                        for attr, value in child.attrs.items():
                            if any(ext in str(value).lower() for ext in ['.mp3', '.wav', '.m4a']) and 'http' in str(value):
                                download_link = urljoin(url, str(value))
                                print(f"   ✅ Tìm thấy trong child: {download_link}")
                                break
                        if download_link:
                            break
                
                if download_link:
                    music_items.append({
                        'title': title,
                        'download_url': download_link,
                        'index': len(music_items) + 1
                    })
                    print(f"   ✅ Đã thêm vào danh sách: {title}")
                else:
                    print(f"   ❌ Không tìm thấy download link cho item này")
                    
            except Exception as e:
                print(f"⚠️  Lỗi khi parse item {idx}: {e}")
                continue
        
        # Nếu không tìm thấy gì, thử tìm trong JavaScript/JSON data
        if not music_items:
            print("\n🔍 Tìm kiếm trong JavaScript/JSON data...")
            scripts = soup.find_all('script')
            for idx, script in enumerate(scripts[:10]):  # Chỉ check 10 scripts đầu
                if script.string:
                    script_content = script.string
                    
                    # Tìm URLs MP3 trong JavaScript
                    if any(keyword in script_content.lower() for keyword in ['mp3', 'audio', 'music', 'track']):
                        print(f"   📜 Script {idx + 1} có thể chứa thông tin audio...")
                        
                        # Patterns để extract URLs
                        url_patterns = [
                            r'["\']([^"\']*\.mp3[^"\']*)["\']',
                            r'["\']([^"\']*\.wav[^"\']*)["\']',
                            r'["\']([^"\']*\.m4a[^"\']*)["\']',
                            r'["\']([^"\']*audio[^"\']*\.mp3)["\']',
                            r'download["\']:\s*["\']([^"\']*)["\']',
                            r'src["\']:\s*["\']([^"\']*\.mp3[^"\']*)["\']'
                        ]
                        
                        for pattern in url_patterns:
                            urls = re.findall(pattern, script_content, re.IGNORECASE)
                            for url_match in urls:
                                if url_match and len(url_match) > 10:  # Filter out short false matches
                                    full_url = urljoin(url, url_match)
                                    music_items.append({
                                        'title': f"JS Track {len(music_items) + 1}",
                                        'download_url': full_url,
                                        'index': len(music_items) + 1
                                    })
                                    print(f"   ✅ Tìm thấy URL trong JS: {url_match}")
                        
                        # Tìm thông tin JSON
                        json_patterns = [
                            r'\{[^}]*"title"[^}]*"url"[^}]*\}',
                            r'\{[^}]*"name"[^}]*"src"[^}]*\}',
                            r'\{[^}]*"audio"[^}]*\}'
                        ]
                        
                        for pattern in json_patterns:
                            matches = re.findall(pattern, script_content, re.IGNORECASE)
                            for match in matches:
                                try:
                                    # Thử parse JSON-like structure
                                    if '"title"' in match and '"url"' in match:
                                        title_match = re.search(r'"title":\s*"([^"]*)"', match)
                                        url_match = re.search(r'"url":\s*"([^"]*)"', match)
                                        if title_match and url_match:
                                            music_items.append({
                                                'title': title_match.group(1),
                                                'download_url': urljoin(url, url_match.group(1)),
                                                'index': len(music_items) + 1
                                            })
                                            print(f"   ✅ Tìm thấy JSON track: {title_match.group(1)}")
                                except Exception as e:
                                    print(f"   ⚠️  Lỗi parse JSON: {e}")
        
        print(f"\n📊 Tổng cộng tìm thấy {len(music_items)} tracks")
        return music_items
    
    def _create_demo_list(self) -> List[Dict]:
        """
        Tạo danh sách demo để test tool
        """
        print("🎵 Tạo danh sách demo để test...")
        return [
            {
                'title': 'Demo Piano Track 1',
                'download_url': 'https://pixabay.com/music/download/demo1.mp3',
                'index': 1
            },
            {
                'title': 'Demo Piano Track 2', 
                'download_url': 'https://pixabay.com/music/download/demo2.mp3',
                'index': 2
            },
            {
                'title': 'Demo Piano Track 3',
                'download_url': 'https://pixabay.com/music/download/demo3.mp3', 
                'index': 3
            }
        ]
    
    def display_music_list(self):
        """
        Hiển thị danh sách nhạc với số thứ tự
        """
        if not self.music_list:
            print("📭 Không có nhạc nào trong danh sách")
            return
            
        print("\n" + "="*80)
        print("🎵 DANH SÁCH NHẠC TÌM THẤY")
        print("="*80)
        
        current_page = None
        for item in self.music_list:
            # Hiển thị header cho trang mới
            if 'page' in item and item['page'] != current_page:
                current_page = item['page']
                if current_page > 1:
                    print(f"\n📄 --- TRANG {current_page} ---")
            
            page_info = f" (Trang {item['page']})" if 'page' in item else ""
            print(f"{item['index']:3d}. {item['title']}{page_info}")
            print(f"     URL: {item['download_url'][:60]}...")
            print()
    
    def _try_get_real_download_url(self, fake_url: str, title: str) -> str:
        """
        Thử lấy URL download thực từ Pixabay
        """
        try:
            print(f"   🔍 Thử lấy URL thực cho: {title}")
            
            # Nếu là detail page, thử fetch và tìm download link
            if '/music/' in fake_url and not fake_url.endswith('.mp3'):
                print(f"   📄 Fetching detail page: {fake_url}")
                
                # Thêm headers để giả lập browser
                headers = {
                    'Referer': 'https://pixabay.com/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                
                response = self.session.get(fake_url, timeout=15, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    print(f"   📊 Detail page size: {len(response.content):,} bytes")
                    
                    # Tìm trong JavaScript data
                    scripts = soup.find_all('script')
                    for script in scripts:
                        if script.string:
                            script_content = script.string
                            
                            # Tìm URLs MP3 trong JavaScript với patterns mạnh hơn
                            patterns = [
                                r'"download"[^"]*"([^"]*\.mp3[^"]*)"',
                                r'"url"[^"]*"([^"]*\.mp3[^"]*)"',
                                r'"src"[^"]*"([^"]*\.mp3[^"]*)"',
                                r'cdn\.pixabay\.com/audio/[^"\']*\.mp3',
                                r'https://[^"\']*\.mp3',
                                r'["\']([^"\']*cdn\.pixabay\.com[^"\']*\.mp3)["\']'
                            ]
                            
                            for pattern in patterns:
                                matches = re.findall(pattern, script_content, re.IGNORECASE)
                                for match in matches:
                                    if match and len(match) > 20 and '.mp3' in match:
                                        if not match.startswith('http'):
                                            match = 'https:' + match if match.startswith('//') else 'https://' + match
                                        print(f"   ✅ Tìm thấy URL trong JS: {match}")
                                        return match
                    
                    # Tìm audio elements và download buttons
                    download_patterns = [
                        'audio[src]',
                        'source[src]',
                        'a[href*=".mp3"]',
                        '[data-url*=".mp3"]',
                        '[onclick*=".mp3"]'
                    ]
                    
                    for pattern in download_patterns:
                        elements = soup.select(pattern)
                        for elem in elements:
                            url_attrs = ['src', 'href', 'data-url', 'onclick']
                            for attr in url_attrs:
                                href = elem.get(attr, '')
                                if href and '.mp3' in href:
                                    if 'javascript:' not in href.lower():
                                        real_url = urljoin(fake_url, href)
                                        print(f"   ✅ Tìm thấy URL từ {pattern}: {real_url}")
                                        return real_url
                    
                    print(f"   ❌ Không tìm thấy URL download trong detail page")
            
            # Nếu là URL giả định, thử test nó
            elif fake_url.endswith('.mp3'):
                print(f"   🧪 Test URL giả định: {fake_url}")
                try:
                    head_response = self.session.head(fake_url, timeout=8)
                    if head_response.status_code == 200:
                        content_type = head_response.headers.get('content-type', '')
                        if 'audio' in content_type.lower() or 'mpeg' in content_type.lower():
                            print(f"   ✅ URL giả định hoạt động!")
                            return fake_url
                    print(f"   ❌ URL giả định không hoạt động: {head_response.status_code}")
                except:
                    print(f"   ❌ Không thể test URL giả định")
                    
        except Exception as e:
            print(f"   ⚠️  Lỗi khi lấy URL thực: {e}")
        
        # Fallback: return detail page để có thể thử manual
        print(f"   🔄 Fallback: sử dụng detail page")
        return fake_url

    def _get_next_file_index(self, download_folder: str) -> int:
        """
        Kiểm tra thư mục và trả về số thứ tự tiếp theo để tránh ghi đè file cũ
        """
        if not os.path.exists(download_folder):
            return 1
        
        max_index = 0
        try:
            files = os.listdir(download_folder)
            for filename in files:
                if filename.endswith('.mp3'):
                    # Tìm pattern 001_, 002_, etc.
                    match = re.match(r'^(\d{3})_', filename)
                    if match:
                        index = int(match.group(1))
                        max_index = max(max_index, index)
            
            print(f"📂 Tìm thấy {len([f for f in files if f.endswith('.mp3')])} file MP3 trong thư mục")
            if max_index > 0:
                print(f"📊 Số thứ tự cao nhất hiện tại: {max_index}")
                print(f"🆕 File mới sẽ bắt đầu từ: {max_index + 1}")
            
        except Exception as e:
            print(f"⚠️  Lỗi khi scan thư mục: {e}")
        
        return max_index + 1

    def _download_single_file(self, item: Dict, download_folder: str, file_number: int) -> Dict:
        """
        Download một file nhạc đơn lẻ - dùng cho threading
        Returns: Dict với thông tin kết quả download
        """
        result = {
            'item': item,
            'success': False,
            'error': None,
            'filename': None,
            'file_size': 0
        }
        
        try:
            # Làm sạch tên file
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', item['title'])
            filename = f"{file_number:03d}_{safe_title}.mp3"
            filepath = os.path.join(download_folder, filename)
            result['filename'] = filename
            
            with self.print_lock:
                print(f"⬇️  [{threading.current_thread().name}] Đang download {item['index']}: {item['title']}")
            
            # Thử lấy URL thực trước khi download
            real_url = self._try_get_real_download_url(item['download_url'], item['title'])
            
            # Tạo session riêng cho thread này để tránh xung đột
            thread_session = requests.Session()
            thread_session.headers.update(self.session.headers)
            
            # Download file
            with self.print_lock:
                print(f"   🌐 [{threading.current_thread().name}] Downloading từ: {real_url}")
            
            response = thread_session.get(real_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Kiểm tra content type
            content_type = response.headers.get('content-type', '')
            if 'audio' not in content_type.lower() and 'mpeg' not in content_type.lower():
                with self.print_lock:
                    print(f"⚠️  [{threading.current_thread().name}] Cảnh báo: File có thể không phải MP3 (Content-Type: {content_type})")
            
            # Lưu file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(filepath)
            result['file_size'] = file_size
            
            if file_size > 1024 * 1024:  # > 1MB
                size_str = f"{file_size / (1024*1024):.1f}MB"
            else:
                size_str = f"{file_size:,} bytes"
            
            with self.print_lock:
                print(f"✅ [{threading.current_thread().name}] Hoàn thành: {filename} ({size_str})")
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            with self.print_lock:
                print(f"❌ [{threading.current_thread().name}] Lỗi download {item['title']}: {e}")
        
        return result

    def download_music_range(self, start_idx: int, end_idx: int, download_folder: str = "downloads", max_workers: int = 4):
        """
        Download nhạc theo range từ start_idx đến end_idx sử dụng multi-threading
        max_workers: Số thread tối đa (mặc định 4)
        """
        if not self.music_list:
            print("❌ Chưa có danh sách nhạc. Vui lòng parse trang trước.")
            return
        
        # Validate range
        if start_idx < 1 or end_idx > len(self.music_list) or start_idx > end_idx:
            print(f"❌ Range không hợp lệ. Vui lòng chọn từ 1 đến {len(self.music_list)}")
            return
        
        # Tạo folder download
        os.makedirs(download_folder, exist_ok=True)
        
        # Kiểm tra thư mục và lấy số thứ tự tiếp theo
        next_file_index = self._get_next_file_index(download_folder)
        
        # Tính toán số file cần download
        total_files = end_idx - start_idx + 1
        
        print(f"\n🚀 Bắt đầu download từ {start_idx} đến {end_idx} ({total_files} files)")
        print(f"📁 Thư mục lưu: {download_folder}")
        print(f"🧵 Sử dụng {max_workers} threads song song")
        if next_file_index > 1:
            print(f"🔢 Số thứ tự file sẽ bắt đầu từ: {next_file_index}")
        print("-" * 60)
        
        # Chuẩn bị danh sách download jobs
        download_jobs = []
        for i in range(start_idx - 1, end_idx):
            if i >= len(self.music_list):
                break
            
            item = self.music_list[i]
            file_number = next_file_index + (i - (start_idx - 1))
            download_jobs.append((item, file_number))
        
        print(f"📋 Đã chuẩn bị {len(download_jobs)} jobs download...")
        
        # Khởi tạo counters
        success_count = 0
        failed_count = 0
        completed_count = 0
        
        # Sử dụng ThreadPoolExecutor để download song song
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Downloader") as executor:
            # Submit tất cả jobs
            future_to_job = {
                executor.submit(self._download_single_file, item, download_folder, file_number): (item, file_number) 
                for item, file_number in download_jobs
            }
            
            print(f"🎯 Đã submit {len(future_to_job)} download tasks...")
            print("⏳ Đang download... (có thể mất vài phút)")
            print("-" * 60)
            
            # Xử lý kết quả khi các thread hoàn thành
            for future in as_completed(future_to_job):
                item, file_number = future_to_job[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    
                    with self.progress_lock:
                        if result['success']:
                            success_count += 1
                        else:
                            failed_count += 1
                        
                        # Hiển thị tiến độ
                        progress = (completed_count / len(download_jobs)) * 100
                        print(f"\n📊 Tiến độ: {completed_count}/{len(download_jobs)} ({progress:.1f}%)")
                        print(f"✅ Thành công: {success_count} | ❌ Thất bại: {failed_count}")
                        
                except Exception as e:
                    with self.print_lock:
                        print(f"❌ Lỗi unexpected khi xử lý {item['title']}: {e}")
                    failed_count += 1
        
        print(f"\n" + "="*60)
        print(f"🏁 HOÀN THÀNH DOWNLOAD")
        print(f"📊 KẾT QUẢ CUỐI CÙNG:")
        print(f"   ✅ Thành công: {success_count}/{len(download_jobs)}")
        print(f"   ❌ Thất bại: {failed_count}/{len(download_jobs)}")
        print(f"   📊 Tỷ lệ thành công: {(success_count/len(download_jobs)*100):.1f}%")
        print(f"📁 Thư mục: {os.path.abspath(download_folder)}")
        print("="*60)

def handle_direct_urls():
    """
    Xử lý download từ URL trực tiếp
    """
    print("\n📥 DOWNLOAD TRỰC TIẾP TỪ URL")
    print("=" * 50)
    print("Nhập các URL file MP3, mỗi URL một dòng.")
    print("Nhập 'done' để hoàn thành:")
    
    urls = []
    while True:
        url = input(f"URL {len(urls) + 1}: ").strip()
        if url.lower() == 'done':
            break
        if url:
            urls.append(url)
    
    if not urls:
        print("❌ Không có URL nào được nhập.")
        return
    
    # Tạo downloader và fake music list
    downloader = PixabayMusicDownloader()
    downloader.music_list = [
        {
            'title': f'Direct Download {i+1}',
            'download_url': url,
            'index': i + 1
        } for i, url in enumerate(urls)
    ]
    
    # Hiển thị và download
    downloader.display_music_list()
    
    try:
        print(f"\n📝 Download tất cả {len(urls)} file?")
        folder_input = input("Thư mục lưu (Enter = 'downloads'): ").strip()
        folder = folder_input if folder_input else "downloads"
        
        confirm = input(f"\nXác nhận download {len(urls)} file vào '{folder}'? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes']:
            downloader.download_music_range(1, len(urls), folder)
        else:
            print("❌ Đã hủy download.")
            
    except KeyboardInterrupt:
        print("\n\n❌ Đã hủy bởi người dùng.")
    except Exception as e:
        print(f"❌ Lỗi: {e}")

def main():
    """
    Hàm main để chạy tool
    """
    downloader = PixabayMusicDownloader()
    
    print("🎵 PIXABAY MUSIC DOWNLOADER")
    print("=" * 50)
    
    # URL mặc định từ user
    default_url = "https://pixabay.com/vi/music/search/nh%e1%ba%a1c%20kh%c3%b4ng%20b%e1%ba%a3n%20quy%e1%bb%81n/?genre=piano+solo"
    
    # Nhập URL (hoặc dùng mặc định)
    url_input = input(f"Nhập URL Pixabay (Enter để dùng mặc định):\n{default_url}\n> ").strip()
    url = url_input if url_input else default_url
    
    # Hỏi về pagination
    print("\n🔄 TÙY CHỌN CRAWLING:")
    print("1. Chỉ crawl trang đầu tiên (nhanh)")
    print("2. Crawl nhiều trang (chậm hơn nhưng có nhiều nhạc hơn)")
    
    crawl_choice = input("Chọn (1/2, Enter = 1): ").strip()
    
    if crawl_choice == '2':
        try:
            start_page = int(input("Từ trang (Enter = 1): ").strip() or "1")
            end_page = int(input("Đến trang (Enter = 3): ").strip() or "3")
            
            # Validate input
            start_page = max(start_page, 1)  # Tối thiểu trang 1
            end_page = min(max(end_page, start_page), 100)  # Tối đa trang 100
            
            if start_page > end_page:
                start_page, end_page = end_page, start_page  # Swap nếu ngược
            
            total_pages = end_page - start_page + 1
            
            # Tùy chọn threads cho parsing
            if total_pages > 1:
                parse_threads_input = input(f"Số threads cho parsing (Enter = 3, tối đa 5): ").strip()
                try:
                    parse_threads = int(parse_threads_input) if parse_threads_input else 3
                    parse_threads = min(max(parse_threads, 1), 5)  # Giới hạn từ 1-5
                except ValueError:
                    parse_threads = 3
                    print("❌ Số không hợp lệ, dùng mặc định 3 threads")
                
                print(f"🚀 Sẽ crawl từ trang {start_page} đến trang {end_page} ({total_pages} trang) với {parse_threads} threads...")
                music_list = downloader.parse_multiple_pages(url, start_page, end_page, parse_threads)
            else:
                print(f"🚀 Sẽ crawl từ trang {start_page} đến trang {end_page} ({total_pages} trang)...")
                music_list = downloader.parse_multiple_pages(url, start_page, end_page, 1)
        except ValueError:
            print("❌ Số không hợp lệ, dùng mặc định trang 1-3")
            music_list = downloader.parse_multiple_pages(url, 1, 3, 3)
    else:
        print("🚀 Crawl trang đầu tiên...")
        music_list = downloader.parse_pixabay_page(url)
    
    if not music_list:
        print("❌ Không thể lấy danh sách nhạc từ trang này.")
        
        # Cho phép người dùng thử lại với URL khác
        while True:
            choice = input("""
🔄 Bạn muốn:
1. Thử lại với URL khác
2. Nhập trực tiếp URL file MP3
3. Thoát
Chọn (1/2/3): """).strip()
            
            if choice == '1':
                new_url = input("Nhập URL mới: ").strip()
                if new_url:
                    music_list = downloader.parse_pixabay_page(new_url)
                    if music_list:
                        break
            elif choice == '2':
                return handle_direct_urls()
            elif choice == '3':
                print("👋 Tạm biệt!")
                return
            else:
                print("❌ Vui lòng chọn 1, 2 hoặc 3.")
        
        if not music_list:
            return
    
    # Hiển thị danh sách
    downloader.display_music_list()
    
    # Nhập range để download
    try:
        print(f"\n📝 Nhập range để download (1-{len(music_list)}):")
        start = int(input("Từ số: ").strip())
        end = int(input("Đến số: ").strip())
        
        # Nhập thư mục lưu (optional)
        folder_input = input("Thư mục lưu (Enter = 'downloads'): ").strip()
        folder = folder_input if folder_input else "downloads"
        
        # Tùy chọn số threads
        print(f"\n⚙️  TÙY CHỌN THREADING:")
        threads_input = input("Số threads download (Enter = 4, tối đa 8): ").strip()
        try:
            max_threads = int(threads_input) if threads_input else 4
            max_threads = min(max(max_threads, 1), 8)  # Giới hạn từ 1-8
        except ValueError:
            max_threads = 4
            print("❌ Số không hợp lệ, dùng mặc định 4 threads")
        
        # Xác nhận
        print(f"\n🔍 SẼ DOWNLOAD:")
        print(f"   - Từ bài {start} đến bài {end}")
        print(f"   - Tổng cộng: {end - start + 1} bài")
        print(f"   - Thư mục: {folder}")
        print(f"   - Threads: {max_threads}")
        
        confirm = input("\nXác nhận download? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes']:
            downloader.download_music_range(start, end, folder, max_threads)
        else:
            print("❌ Đã hủy download.")
            
    except KeyboardInterrupt:
        print("\n\n❌ Đã hủy bởi người dùng.")
    except ValueError:
        print("❌ Vui lòng nhập số hợp lệ.")
    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    main()
