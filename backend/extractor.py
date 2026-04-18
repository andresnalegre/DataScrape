import os
import logging
import requests
from collections import deque
from urllib.parse import urlparse, urljoin, urlunparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

MAX_RESOURCE_SIZE_BYTES = 10 * 1024 * 1024


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

    def crawl(self):
        queue = deque()
        queue.append((self.base_url, 0))
        pages_done = 0

        while queue:
            if self.stop_flag and self.stop_flag():
                self._emit("Crawling stopped by user.")
                break

            url, depth = queue.popleft()

            if depth > self.max_depth:
                continue
            if pages_done >= self.max_pages:
                self._emit(f"Reached page limit ({self.max_pages}). Stopping.")
                break

            self._emit(f"[{pages_done + 1}/{self.max_pages}] Scraping: {url}")
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

    def _fetch_page(self, url):
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            html_content = self.driver.page_source
            if not html_content:
                self._emit(f"No content at: {url}")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')
            links = self._collect_links(soup, url)
            self._process_resources(soup, url, self.save_dir)

            if self.stop_flag and self.stop_flag():
                return None

            filename = self._create_filename(url)
            self._save_html(str(soup), self.save_dir, filename)

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
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            full_url = self._normalize_url(urljoin(current_url, href))
            parsed = urlparse(full_url)
            if parsed.netloc == self.base_domain:
                links.append(full_url)
        return links

    def _create_filename(self, url):
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        name = f"{parsed.netloc}_{path.replace('/', '_')}.html" if path else "index.html"
        return name[:200]

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
                if resource_url.startswith(('data:', '#', 'javascript:')):
                    continue
                full_url = urljoin(base_url, resource_url)
                filename = os.path.basename(urlparse(full_url).path)
                if not filename:
                    continue
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