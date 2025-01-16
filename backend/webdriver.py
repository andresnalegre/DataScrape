import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.firefox import GeckoDriverManager
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

CHROMEDRIVER_PATH = "./CromeDriver/131.0.6778.204/chromedriver-mac-arm64/chromedriver"

def get_chrome_driver(headless=True, additional_args=None):
    try:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        if additional_args:
            for arg in additional_args:
                options.add_argument(arg)

        service = ChromeService(executable_path=CHROMEDRIVER_PATH)
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
    _driver: WebDriver | None = None

    @staticmethod
    def get_driver(browser="chrome", headless=True, additional_args=None):
        if WebDriverManager._driver is None:
            WebDriverManager._driver = get_webdriver(browser=browser, headless=headless, additional_args=additional_args)
            logging.info(f"WebDriver created for browser: {browser}")
        return WebDriverManager._driver

    @staticmethod
    def quit_driver():
        if WebDriverManager._driver is not None:
            logging.info("Closing the WebDriver.")
            WebDriverManager._driver.quit()
            WebDriverManager._driver = None
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
