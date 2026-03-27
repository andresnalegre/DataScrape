import os
from PyQt5.QtWidgets import (
    QMainWindow, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget, QFileDialog,
)
from PyQt5.QtCore import QThread, pyqtSignal
from backend.extractor import runExtractor
from backend.webdriver import WebDriverManager
from frontend.logics import UiLogic


class ScraperWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, url, directory, driver):
        super().__init__()
        self.url = url
        self.directory = directory
        self.driver = driver

    def run(self):
        try:
            extractor = runExtractor(self.url, self.directory, self.driver)
            result = extractor.extract_link(self.url)
            if result:
                self.log_signal.emit("Scraping completed successfully.")
                self.finished_signal.emit(True)
            else:
                self.log_signal.emit("Scraping finished with no data.")
                self.finished_signal.emit(False)
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DataScrape")
        self.setGeometry(300, 200, 600, 400)

        layout = QVBoxLayout()

        self.url_label = QLabel("Enter Website URL:")
        layout.addWidget(self.url_label)

        self.url_input = QLineEdit(self)
        layout.addWidget(self.url_input)

        self.dir_label = QLabel("Select Directory to Save:")
        layout.addWidget(self.dir_label)

        self.dir_button = QPushButton("Choose Directory", self)
        self.dir_button.setObjectName("dir_button")
        self.dir_button.clicked.connect(self.select_directory)
        layout.addWidget(self.dir_button)

        self.selected_dir_label = QLabel("No directory selected", self)
        layout.addWidget(self.selected_dir_label)

        self.start_button = QPushButton("Start Scraping")
        self.start_button.clicked.connect(self.start_scraping)
        layout.addWidget(self.start_button)

        self.log_output = QTextEdit(self)
        self.log_output.setObjectName("log_output")
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.selected_directory = None
        self.logic = UiLogic(self.log_output, self)
        self.worker = None

        self._init_driver()

    def _init_driver(self):
        try:
            self.log_output.append("Initializing WebDriver...")
            self.driver = WebDriverManager.get_driver(browser="chrome")
            self.log_output.append("WebDriver ready.")
        except Exception as e:
            self.driver = None
            self.log_output.append(f"WebDriver failed to initialize: {str(e)}")
            self.start_button.setEnabled(False)

    def select_directory(self):
        directory = self.logic.select_directory()
        if directory:
            self.selected_dir_label.setText(f"Selected Directory: {directory}")
            self.selected_directory = directory

    def start_scraping(self):
        url = self.url_input.text().strip()
        directory_name = self.selected_directory

        if not self.logic.verify_input(url, directory_name):
            return

        if self.driver is None:
            self.log_output.append("WebDriver is not available. Cannot scrape.")
            return

        self.log_output.append(f"Starting scraping for URL: {url}")
        self.start_button.setEnabled(False)
        self.start_button.setText("Scraping...")

        self.worker = ScraperWorker(url, directory_name, self.driver)
        self.worker.log_signal.connect(self.log_output.append)
        self.worker.finished_signal.connect(self._on_scraping_finished)
        self.worker.start()

    def _on_scraping_finished(self, success):
        self.start_button.setEnabled(True)
        self.start_button.setText("Start Scraping")