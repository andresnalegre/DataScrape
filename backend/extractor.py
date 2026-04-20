import os
import re
import logging
import requests
from collections import deque
from urllib.parse import urlparse, urljoin, urlunparse, unquote
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

MAX_RESOURCE_SIZE_BYTES = 10 * 1024 * 1024

NON_HTML_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.rtf', '.epub', '.mobi',
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',
    '.tiff', '.tif', '.heic', '.raw', '.psd', '.ai', '.eps',
    '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v',
    '.mp3', '.wav', '.ogg', '.flac', '.aac', '.wma', '.m4a',
    '.zip', '.rar', '.gz', '.tar', '.7z', '.bz2', '.dmg', '.iso',
    '.exe', '.msi', '.apk', '.pkg', '.deb',
    '.css', '.js', '.json', '.xml', '.csv', '.yaml', '.yml',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.rss', '.atom', '.txt', '.log', '.map',
}

SKIP_URL_PATTERNS = [
    r'(logout|log-out|signout|sign-out)',
    r'\?.*print=',
    r'\?.*download=',
    r'/cdn-cgi/',
    r'/wp-json/',
    r'/wp-admin/',
    r'/feed/?$',
    r'\.php\?.*action=',
    r'\?replytocom=',
    r'\?share=',
    r'\?like_comment=',
    r'chrome-extension://',
    r'^mailto:', r'^tel:', r'^sms:', r'^ftp:',
]

_skip_compiled = [re.compile(p, re.IGNORECASE) for p in SKIP_URL_PATTERNS]

DOWNLOADABLE_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.epub', '.mobi', '.rtf', '.odt', '.ods', '.odp',
    '.zip', '.rar', '.gz', '.tar', '.7z',
    '.mp3', '.mp4', '.wav', '.avi', '.mov',
}


def _is_crawlable(url):
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext in NON_HTML_EXTENSIONS:
        return False
    for pattern in _skip_compiled:
        if pattern.search(url):
            return False
    return True


def _sanitize_filename(name):
    name = unquote(name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = name.strip('. ')
    return name[:180] or "unnamed"


class Extractor:
    def __init__(self, base_url, save_dir, driver, timeout=30,
                 stop_flag=None, max_pages=50, max_depth=3,
                 progress_callback=None, log_callback=None):
        self.base_url = self._normalize_url(base_url)
        self.base_domain = urlparse(self.base_url).netloc
        self.save_dir = save_dir
        self.timeout = timeout
        self.driver = driver
        self.stop_flag = stop_flag
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.visited = set()
        self.visited.add(self.base_url)
        os.makedirs(self.save_dir, exist_ok=True)

    def _emit(self, message):
        logging.info(message)
        if self.log_callback:
            self.log_callback(message)

    def _fetch_sitemap_urls(self):
        urls = set()
        candidates = [
            self.base_url.rstrip('/') + '/sitemap.xml',
            self.base_url.rstrip('/') + '/sitemap_index.xml',
            self.base_url.rstrip('/') + '/sitemap/',
        ]
        for sitemap_url in candidates:
            try:
                resp = requests.get(sitemap_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; DataScrape/2.0)'
                })
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.content, 'xml')
                locs = soup.find_all('loc')
                if not locs:
                    continue
                for loc in locs:
                    url = loc.get_text(strip=True)
                    if url.endswith('.xml'):
                        try:
                            sub = requests.get(url, timeout=10)
                            if sub.status_code == 200:
                                sub_soup = BeautifulSoup(sub.content, 'xml')
                                for sub_loc in sub_soup.find_all('loc'):
                                    sub_url = sub_loc.get_text(strip=True)
                                    parsed = urlparse(sub_url)
                                    if parsed.netloc == self.base_domain and _is_crawlable(sub_url):
                                        urls.add(self._normalize_url(sub_url))
                        except Exception:
                            pass
                    else:
                        parsed = urlparse(url)
                        if parsed.netloc == self.base_domain and _is_crawlable(url):
                            urls.add(self._normalize_url(url))
                if urls:
                    self._emit(f"Sitemap found: {len(urls)} URL(s) discovered.")
                    return urls
            except Exception:
                pass
        return urls

    def crawl(self):
        queue = deque()
        queue.append((self.base_url, 0))
        pages_done = 0

        sitemap_urls = self._fetch_sitemap_urls()
        if sitemap_urls:
            for url in sitemap_urls:
                if url not in self.visited:
                    self.visited.add(url)
                    queue.append((url, 1))

        while queue:
            if self.stop_flag and self.stop_flag():
                self._emit("Crawling stopped by user.")
                break

            url, depth = queue.popleft()

            if depth > self.max_depth:
                continue
            if pages_done >= self.max_pages:
                self._emit("Reached page limit. Stopping.")
                break

            if not _is_crawlable(url):
                continue

            self._emit(f"[{pages_done + 1}] Scraping: {url}")
            result = self._fetch_page(url)

            if result is None:
                continue

            pages_done += 1

            if self.progress_callback:
                progress = int((pages_done / self.max_pages) * 100)
                self.progress_callback(min(progress, 99))

            if depth < self.max_depth:
                for link in result["links"]:
                    if link not in self.visited:
                        self.visited.add(link)
                        queue.append((link, depth + 1))

        if self.progress_callback:
            self.progress_callback(100)

        self._emit(f"Crawling complete. {pages_done} page(s) collected.")
        return pages_done

    def _page_save_dir(self, url):
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if path:
            folder = _sanitize_filename(path.replace('/', '_'))
        else:
            folder = "index"
        page_dir = os.path.join(self.save_dir, folder)
        os.makedirs(page_dir, exist_ok=True)
        return page_dir

    def _fetch_page(self, url):
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            try:
                import time
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                self.driver.execute_script("""
                    document.querySelectorAll('canvas').forEach(function(c) {
                        try {
                            var dataUrl = c.toDataURL();
                            if (dataUrl && dataUrl !== 'data:,') {
                                c.setAttribute('data-snapshot', dataUrl);
                                c.style.backgroundImage = 'url(' + dataUrl + ')';
                                c.style.backgroundSize = 'cover';
                            }
                        } catch(e) {}
                    });
                """)
            except Exception:
                pass

            html_content = self.driver.page_source
            if not html_content:
                self._emit(f"No content at: {url}")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')
            links = self._collect_links(soup, url)

            page_dir = self._page_save_dir(url)
            self._process_resources(soup, url, page_dir)

            # Extract real src from live DOM (handles lazy loading)
            try:
                live_imgs = self.driver.execute_script("""
                    var imgs = document.querySelectorAll('img');
                    var result = [];
                    imgs.forEach(function(img) {
                        if (img.currentSrc) result.push(img.currentSrc);
                        else if (img.src) result.push(img.src);
                    });
                    return result;
                """)
                if live_imgs:
                    for img_url in live_imgs:
                        if not img_url or img_url.startswith(('data:', 'blob:', 'chrome-extension:')):
                            continue
                        raw_name = os.path.basename(urlparse(img_url).path)
                        if not raw_name:
                            continue
                        filename = _sanitize_filename(raw_name)
                        save_path = os.path.join(page_dir, filename)
                        if not os.path.exists(save_path):
                            self._download_file_direct(img_url, save_path)
                        soup_img = soup.find('img', src=lambda s: s and os.path.basename(urlparse(urljoin(url, s)).path) == os.path.basename(urlparse(img_url).path))
                        if soup_img:
                            soup_img['src'] = filename
            except Exception as e:
                logging.warning(f"Live DOM extraction failed: {e}")

            if self.stop_flag and self.stop_flag():
                return None

            self._save_html(str(soup), page_dir, "index.html")

            return {"html": str(soup), "links": links}

        except TimeoutException:
            self._emit(f"Timeout: {url}")
        except WebDriverException as e:
            self._emit(f"WebDriver error at {url}: {e}")
        except Exception as e:
            self._emit(f"Error at {url}: {e}")
        return None

    def _collect_links(self, soup, current_url):
        links = []
        for tag in soup.find_all('a', href=True):
            href = tag['href'].strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'sms:', 'ftp:')):
                continue
            full_url = self._normalize_url(urljoin(current_url, href))
            parsed = urlparse(full_url)
            if parsed.netloc != self.base_domain:
                continue
            ext = os.path.splitext(parsed.path)[1].lower()
            if ext in DOWNLOADABLE_EXTENSIONS:
                self._download_file(full_url)
                continue
            if not _is_crawlable(full_url):
                continue
            links.append(full_url)
        return links

    def _download_file(self, url):
        try:
            filename = _sanitize_filename(os.path.basename(urlparse(url).path))
            if not filename:
                return
            save_path = os.path.join(self.save_dir, filename)
            if os.path.exists(save_path):
                return
            self._emit(f"Downloading file: {filename}")
            response = requests.get(url, stream=True, timeout=15)
            response.raise_for_status()
            size = 0
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.stop_flag and self.stop_flag():
                        return
                    size += len(chunk)
                    if size > MAX_RESOURCE_SIZE_BYTES:
                        logging.warning(f"File too large, aborting: {url}")
                        return
                    f.write(chunk)
            self._emit(f"Saved file: {filename}")
        except Exception as e:
            logging.error(f"Failed to download file {url}: {e}")

    def _download_file_direct(self, url, save_path):
        try:
            response = requests.get(url, stream=True, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            logging.error(f"Failed to download {url}: {e}")

    def _save_html(self, html_content, save_dir, filename):
        try:
            file_path = os.path.join(save_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info(f"Saved: {file_path}")
        except Exception as e:
            logging.error(f"Error saving HTML: {e}")

    def _download_resource(self, element, attr, full_url, save_path):
        if self.stop_flag and self.stop_flag():
            return
        try:
            response = requests.get(full_url, stream=True, timeout=10)
            response.raise_for_status()

            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_RESOURCE_SIZE_BYTES:
                logging.warning(f"Skipping large resource: {full_url}")
                return

            size = 0
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.stop_flag and self.stop_flag():
                        return
                    size += len(chunk)
                    if size > MAX_RESOURCE_SIZE_BYTES:
                        logging.warning(f"Resource too large, aborting: {full_url}")
                        return
                    f.write(chunk)

            element[attr] = os.path.basename(save_path)
        except Exception as e:
            logging.error(f"Failed to download resource {full_url}: {e}")

    def _process_resources(self, soup, base_url, save_dir):
        resource_tags = {'link': 'href', 'script': 'src', 'img': 'src'}
        tasks = []

        for tag, attr in resource_tags.items():
            for element in soup.find_all(tag):
                resource_url = element.get(attr)
                if not resource_url:
                    continue
                if resource_url.startswith(('data:', '#', 'javascript:', 'chrome-extension:')):
                    continue
                full_url = urljoin(base_url, resource_url)
                raw_name = os.path.basename(urlparse(full_url).path)
                if not raw_name:
                    continue
                filename = _sanitize_filename(raw_name)
                save_path = os.path.join(save_dir, filename)
                tasks.append((element, attr, full_url, save_path))

        for element in soup.find_all(True):
            for attr in ('srcset', 'data-src', 'data-srcset', 'data-lazy-src'):
                val = element.get(attr)
                if not val:
                    continue
                if val.startswith(('data:', '#', 'javascript:', 'chrome-extension:')):
                    continue
                src = val.split()[0].rstrip(',')
                full_url = urljoin(base_url, src)
                raw_name = os.path.basename(urlparse(full_url).path)
                if not raw_name:
                    continue
                filename = _sanitize_filename(raw_name)
                save_path = os.path.join(save_dir, filename)
                tasks.append((element, attr, full_url, save_path))

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(self._download_resource, el, attr, url, path)
                for el, attr, url, path in tasks
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Resource download error: {e}")

    def _normalize_url(self, url):
        url = url.strip()
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"http://{url}"
            parsed = urlparse(url)
        return urlunparse(parsed._replace(
            path=parsed.path.rstrip('/'),
            fragment=''
        ))