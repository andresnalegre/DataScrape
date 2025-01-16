import os
import time
import random
import logging
import requests
from urllib.parse import urlparse, urljoin, urlunparse
from bs4 import BeautifulSoup #type: ignore
from backend.webdriver import WebDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class runExtractor:
    def __init__(self, base_url, save_dir, timeout=30, browser="chrome"):
        self.base_url = self._normalize_url(base_url)
        self.save_dir = save_dir
        self.timeout = timeout
        self.browser = browser
        self.visited_links = set()
        self.visited_links.add(self.base_url)
        os.makedirs(self.save_dir, exist_ok=True)
        logging.info("Initializing WebDriver...")
        self.driver = WebDriverManager.get_driver(browser=self.browser)

    def extract_link(self, url):
        try:
            url = self._normalize_url(url)
            logging.info(f"Accessing URL: {url}")
            self.driver.get(url)

            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            html_content = self.driver.page_source
            if not html_content:
                logging.error(f"No HTML content retrieved for URL: {url}")
                return None

            logging.info("Page content retrieved successfully.")
            filename = self._create_filename(url)
            self._save_html(html_content, self.save_dir, filename)

            soup = BeautifulSoup(html_content, 'html.parser')
            self._process_resources(soup, self.base_url, self.save_dir)
            self.visited_links.add(url)

            logging.info(f"Extraction completed for URL: {url}")
            return {"html": html_content}

        except TimeoutException:
            logging.error(f"Timeout while accessing URL: {url}")
        except WebDriverException as e:
            logging.error(f"WebDriver error while accessing {url}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while accessing {url}: {e}")
        return None

    def _create_filename(self, url):
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        filename = f"{parsed_url.netloc}_{path.replace('/', '_')}.html" if path else "index.html"
        return filename

    def _save_html(self, html_content, save_dir, filename):
        try:
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info(f"Page saved at: {file_path}")
        except Exception as e:
            logging.error(f"Error saving HTML file: {e}")

    def _process_resources(self, soup, base_url, save_dir):
        resource_tags = {'link': 'href', 'script': 'src', 'img': 'src'}
        for tag, attr in resource_tags.items():
            for element in soup.find_all(tag):
                resource_url = element.get(attr)
                if resource_url:
                    full_url = urljoin(base_url, resource_url)
                    filename = os.path.basename(urlparse(full_url).path)
                    save_path = os.path.join(save_dir, filename)

                    try:
                        response = requests.get(full_url, stream=True, timeout=10)
                        response.raise_for_status()

                        with open(save_path, "wb") as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)

                        element[attr] = filename
                        logging.info(f"Downloaded and updated: {full_url} -> {save_path}")
                    except Exception as e:
                        logging.error(f"Failed to download resource {full_url}: {e}")

    def _normalize_url(self, url):
        url = url.strip()
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"http://{url}"
            parsed = urlparse(url)
        return urlunparse(parsed._replace(path=parsed.path.rstrip('/')))
