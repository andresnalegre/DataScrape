import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from contextlib import contextmanager


MACOS_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _get_chromedriver_path():
    import os, sys, glob
    bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "chromedriver")
    if os.path.isfile(bundled):
        logging.info(f"Using bundled ChromeDriver: {bundled}")
        return bundled
    pattern = os.path.expanduser("~/.wdm/drivers/chromedriver/mac64/*/chromedriver-mac-arm64/chromedriver")
    matches = sorted(glob.glob(pattern), reverse=True)
    if matches:
        logging.info(f"Using cached ChromeDriver: {matches[0]}")
        return matches[0]
    logging.info("Using ChromeDriverManager to fetch driver.")
    return ChromeDriverManager().install()


def get_chrome_driver(headless=True, additional_args=None):
    import os
    try:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        if additional_args:
            for arg in additional_args:
                options.add_argument(arg)

        if os.path.exists(MACOS_CHROME_PATH):
            options.binary_location = MACOS_CHROME_PATH

        driver_path = _get_chromedriver_path()
        service = ChromeService(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)
        logging.info("ChromeDriver started successfully.")
        return driver
    except Exception as e:
        logging.error(f"Error starting ChromeDriver: {e}")
        raise


def get_firefox_driver(headless=True, additional_args=None):
    try:
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        if additional_args:
            for arg in additional_args:
                options.add_argument(arg)

        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)
        logging.info("FirefoxDriver started successfully.")
        return driver
    except Exception as e:
        logging.error(f"Error starting FirefoxDriver: {e}")
        raise


def get_webdriver(browser="chrome", headless=True, additional_args=None):
    try:
        if browser.lower() == "chrome":
            return get_chrome_driver(headless=headless, additional_args=additional_args)
        elif browser.lower() == "firefox":
            return get_firefox_driver(headless=headless, additional_args=additional_args)
        else:
            raise ValueError(f"Browser '{browser}' is not supported.")
    except ValueError as e:
        logging.error(f"Error requesting WebDriver: {e}")
        raise


class WebDriverManager:
    _instance: Optional["WebDriverManager"] = None
    _driver: Optional[WebDriver] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_driver(cls, browser="chrome", headless=True, additional_args=None):
        if cls._driver is None:
            cls._driver = get_webdriver(
                browser=browser,
                headless=headless,
                additional_args=additional_args,
            )
            logging.info(f"WebDriver created for browser: {browser}")
        return cls._driver

    @classmethod
    def quit_driver(cls):
        if cls._driver is not None:
            logging.info("Closing the WebDriver.")
            try:
                cls._driver.quit()
            except Exception as e:
                logging.warning(f"Error while quitting WebDriver: {e}")
            finally:
                cls._driver = None
        else:
            logging.info("No active WebDriver to close.")


@contextmanager
def webdriver_context(browser="chrome", headless=True, additional_args=None):
    driver = get_webdriver(browser=browser, headless=headless, additional_args=additional_args)
    try:
        yield driver
    except Exception as e:
        logging.error(f"Error during WebDriver usage in context: {e}")
        raise
    finally:
        logging.info("Closing WebDriver context.")
        driver.quit()