import os
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QHBoxLayout, QWidget,
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QPixmap
from backend.extractor import Extractor
from backend.webdriver import WebDriverManager
from frontend.logics import UiLogic


class DriverInitWorker(QThread):
    success_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            driver = WebDriverManager.get_driver(browser="chrome")
            self.success_signal.emit(driver)
        except Exception as e:
            self.error_signal.emit(str(e))


class ScraperWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, url, directory, driver):
        super().__init__()
        self.url = url
        self.directory = directory
        self.driver = driver
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            extractor = Extractor(self.url, self.directory, self.driver)
            result = extractor.extract_link(self.url)
            if self._stop:
                self.log_signal.emit("Scraping stopped by user.")
                self.finished_signal.emit(False)
            elif result:
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
        self.setGeometry(300, 200, 600, 500)

        layout = QVBoxLayout()
        layout.setSpacing(8)

        logo_label = QLabel()
        logo_path = self._find_asset('logo.png')
        if logo_path:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaledToHeight(120, Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

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

        button_row = QHBoxLayout()
        self.start_button = QPushButton("Start Scraping")
        self.start_button.clicked.connect(self.start_scraping)
        self.start_button.setEnabled(False)
        button_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.clicked.connect(self.stop_scraping)
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.stop_button)

        layout.addLayout(button_row)

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
        self.driver = None
        self._driver_worker = None

        QTimer.singleShot(0, self._init_driver)

    def _find_asset(self, filename):
        base = os.path.dirname(__file__)
        candidates = [
            os.path.join(base, '..', 'assets', filename),
            os.path.join(base, 'assets', filename),
        ]
        for path in candidates:
            path = os.path.normpath(path)
            if os.path.isfile(path):
                return path
        return None

    def _init_driver(self):
        self.log_output.append("Initializing WebDriver...")
        self._driver_worker = DriverInitWorker()
        self._driver_worker.success_signal.connect(self._on_driver_ready)
        self._driver_worker.error_signal.connect(self._on_driver_error)
        self._driver_worker.start()

    def _on_driver_ready(self, driver):
        self.driver = driver
        self.start_button.setEnabled(True)
        self.log_output.append("Ready to scrape!")

    def _on_driver_error(self, error):
        self.driver = None
        self.log_output.append(f"WebDriver failed to initialize: {error}")
        self.log_output.append("Retry by restarting the application.")

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
        self.stop_button.setEnabled(True)

        self.worker = ScraperWorker(url, directory_name, self.driver)
        self.worker.log_signal.connect(self.log_output.append)
        self.worker.finished_signal.connect(self._on_scraping_finished)
        self.worker.start()

    def stop_scraping(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        self._on_scraping_finished(False)

    def _on_scraping_finished(self, success):
        self.start_button.setEnabled(True)
        self.start_button.setText("Start Scraping")
        self.stop_button.setEnabled(False)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait()
        event.accept()