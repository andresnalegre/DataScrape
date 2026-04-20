import os
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, QProgressBar, QFrame,
    QButtonGroup,
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from backend.extractor import Extractor
from backend.webdriver import WebDriverManager
from frontend.logics import UiLogic

INFINITE_PAGES = 999_999

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
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def __init__(self, url, directory, driver, max_pages=1, max_depth=999):
        super().__init__()
        self.url = url
        self.directory = directory
        self.driver = driver
        self.max_pages = max_pages
        self.max_depth = max_depth
        self._stop = False

    def stop(self):
        self._stop = True

    def _is_stopped(self):
        return self._stop

    def run(self):
        try:
            extractor = Extractor(
                self.url, self.directory, self.driver,
                stop_flag=self._is_stopped,
                max_pages=self.max_pages,
                max_depth=self.max_depth,
                progress_callback=self.progress_signal.emit,
                log_callback=self.log_signal.emit,
            )
            pages = extractor.crawl()
            if self._stop:
                self.finished_signal.emit(False)
            elif pages > 0:
                self.finished_signal.emit(True)
            else:
                self.log_signal.emit("No pages were collected.")
                self.finished_signal.emit(False)
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False)

class ToggleButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setObjectName("toggle_button")
        self.setCursor(Qt.PointingHandCursor)

class PagesSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pages_selector")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        self.custom_pill = QWidget()
        self.custom_pill.setObjectName("custom_pill")
        self.custom_pill.setCursor(Qt.PointingHandCursor)
        pill_layout = QHBoxLayout(self.custom_pill)
        pill_layout.setContentsMargins(16, 0, 16, 0)
        pill_layout.setSpacing(8)

        pages_lbl = QLabel("Pages")
        pages_lbl.setObjectName("pages_pill_label")
        pages_lbl.setStyleSheet(
            "color: #0a84ff; font-size: 12px; font-weight: 600; "
            "text-transform: none; letter-spacing: 0px; padding: 0px; background: transparent;"
        )
        pill_layout.addWidget(pages_lbl)

        self.pages_input = QLineEdit()
        self.pages_input.setObjectName("pages_pill_input")
        self.pages_input.setText("50")
        self.pages_input.setAlignment(Qt.AlignCenter)
        self.pages_input.setFixedWidth(60)
        self.pages_input.setFixedHeight(30)
        pill_layout.addWidget(self.pages_input)

        self.custom_pill.setFixedHeight(44)
        outer.addWidget(self.custom_pill, 2)

        self.infinite_btn = ToggleButton("Infinite")
        self.infinite_btn.setFixedHeight(44)
        self.infinite_btn.clicked.connect(self._on_infinite_clicked)
        outer.addWidget(self.infinite_btn, 3)

        self.custom_pill.mousePressEvent = lambda e: self._on_custom_clicked()

    def _on_infinite_clicked(self):
        self.infinite_btn.setChecked(True)
        self.pages_input.setEnabled(False)
        self.custom_pill.setProperty("dimmed", True)
        self.custom_pill.style().unpolish(self.custom_pill)
        self.custom_pill.style().polish(self.custom_pill)

    def _on_custom_clicked(self):
        self.infinite_btn.setChecked(False)
        self.pages_input.setEnabled(True)
        self.pages_input.setFocus()
        self.pages_input.selectAll()
        self.custom_pill.setProperty("dimmed", False)
        self.custom_pill.style().unpolish(self.custom_pill)
        self.custom_pill.style().polish(self.custom_pill)

    def is_infinite(self):
        return self.infinite_btn.isChecked()

    def get_pages(self):
        text = self.pages_input.text().strip()
        if text.isdigit() and int(text) > 0:
            return int(text)
        return None

    def set_enabled(self, val):
        self.pages_input.setEnabled(val and not self.infinite_btn.isChecked())
        self.infinite_btn.setEnabled(val)
        self.custom_pill.setEnabled(val)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DataScrape")
        self.setMinimumSize(820, 620)

        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().screenGeometry()
        self.resize(900, 680)
        self.move((screen.width() - 900) // 2, max(40, (screen.height() - 680) // 2 - 40))

        root = QWidget()
        root.setStyleSheet("background: #0d0d0f;")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(40, 28, 40, 28)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        header_row.addStretch(1)

        logo_label = QLabel()
        logo_path = self._find_asset('logo.png')
        if logo_path:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaledToHeight(130, Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignCenter)
        header_row.addWidget(logo_label, 0, Qt.AlignCenter)

        header_row.addStretch(1)

        info_btn = QPushButton()
        info_btn.setObjectName("info_btn")
        info_btn.setCursor(Qt.PointingHandCursor)
        info_btn.setFixedSize(32, 32)
        info_btn.clicked.connect(self._open_about)
        info_path = self._find_asset('info.png')
        if info_path:
            info_px = QPixmap(info_path)
            if not info_px.isNull():
                info_px = info_px.scaledToHeight(20, Qt.SmoothTransformation)
                info_btn.setIcon(QIcon(info_px))
                from PyQt5.QtCore import QSize
                info_btn.setIconSize(QSize(20, 20))
        info_btn.setToolTip("About DataScrape")
        header_row.addWidget(info_btn, 0, Qt.AlignTop | Qt.AlignRight)

        root_layout.addLayout(header_row)
        root_layout.addSpacing(10)

        subtitle = QLabel("Extract and save web content easily")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            "color: #636366; font-size: 13px; font-weight: 400; "
            "text-transform: none; letter-spacing: 0px; padding: 0px;"
        )
        root_layout.addWidget(subtitle)
        root_layout.addSpacing(22)

        self._add_divider(root_layout)
        root_layout.addSpacing(20)

        row1 = QHBoxLayout()
        row1.setSpacing(20)

        url_col = QVBoxLayout()
        url_col.setSpacing(6)
        url_col.addWidget(self._field_label("Website URL"))
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.setMinimumHeight(42)
        url_col.addWidget(self.url_input)
        row1.addLayout(url_col, 3)

        dir_col = QVBoxLayout()
        dir_col.setSpacing(6)
        dir_col.addWidget(self._field_label("Save Location"))
        dir_inner = QHBoxLayout()
        dir_inner.setSpacing(8)
        self.selected_dir_label = QLabel("No directory selected")
        self.selected_dir_label.setStyleSheet(
            "color: #48484a; font-size: 12px; font-weight: 400; "
            "text-transform: none; letter-spacing: 0px; padding: 0px;"
        )
        dir_inner.addWidget(self.selected_dir_label, 1)
        self.dir_button = QPushButton("Choose", self)
        self.dir_button.setObjectName("dir_button")
        self.dir_button.setMinimumHeight(42)
        self.dir_button.setFixedWidth(90)
        self.dir_button.clicked.connect(self.select_directory)
        dir_inner.addWidget(self.dir_button)
        dir_col.addLayout(dir_inner)
        row1.addLayout(dir_col, 2)

        root_layout.addLayout(row1)
        root_layout.addSpacing(20)

        root_layout.addWidget(self._field_label("Scraping Mode"))
        root_layout.addSpacing(8)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self.mode_single = ToggleButton("Single Link")
        self.mode_single.setChecked(True)
        self.mode_single.setMinimumHeight(44)
        self.mode_crawl = ToggleButton("Crawling")
        self.mode_crawl.setMinimumHeight(44)
        self._mode_group.addButton(self.mode_single, 0)
        self._mode_group.addButton(self.mode_crawl, 1)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_single)
        mode_row.addWidget(self.mode_crawl)
        root_layout.addLayout(mode_row)
        root_layout.addSpacing(14)

        self.pages_section = QWidget()
        self.pages_section.setStyleSheet("background: transparent;")
        pages_sec_layout = QVBoxLayout(self.pages_section)
        pages_sec_layout.setContentsMargins(0, 0, 0, 0)
        pages_sec_layout.setSpacing(8)
        pages_sec_layout.addWidget(self._field_label("Pages to Collect"))
        self.pages_selector = PagesSelector()
        pages_sec_layout.addWidget(self.pages_selector)

        self.pages_section.setVisible(False)
        root_layout.addWidget(self.pages_section)
        root_layout.addSpacing(20)

        self._add_divider(root_layout)
        root_layout.addSpacing(16)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.setMinimumHeight(44)
        self.stop_button.setFixedWidth(110)
        self.stop_button.clicked.connect(self.stop_scraping)
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.stop_button)

        self.start_button = QPushButton("Start Scraping")
        self.start_button.setObjectName("start_button")
        self.start_button.setMinimumHeight(44)
        self.start_button.clicked.connect(self.start_scraping)
        self.start_button.setEnabled(False)
        button_row.addWidget(self.start_button, 1)

        root_layout.addLayout(button_row)
        root_layout.addSpacing(12)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("progress_bar")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        root_layout.addWidget(self.progress_bar)
        root_layout.addSpacing(16)

        root_layout.addWidget(self._field_label("Activity Log"))
        root_layout.addSpacing(6)
        self.log_output = QTextEdit(self)
        self.log_output.setObjectName("log_output")
        self.log_output.setReadOnly(True)
        root_layout.addWidget(self.log_output, 1)

        self.selected_directory = None
        self.logic = UiLogic(self.log_output, self)
        self.worker = None
        self.driver = None
        self._driver_worker = None

        QTimer.singleShot(0, self._init_driver)

    def _field_label(self, text):
        return QLabel(text)

    def _add_divider(self, layout):
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background: #1c1c1e; border: none; max-height: 1px;")
        layout.addWidget(divider)

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

    def _on_mode_changed(self):
        is_crawl = self._mode_group.checkedId() == 1
        self.pages_section.setVisible(is_crawl)

    def _init_driver(self):
        self.log_output.clear()
        self._boot_steps = [
            self._check_initializing,
            self._check_engine,
            self._check_dependencies,
            self._check_setup,
            self._check_almost,
        ]
        self._boot_index = 0
        self._boot_ok = True
        self._boot_timer = QTimer()
        self._boot_timer.timeout.connect(self._run_next_boot_step)
        self._boot_timer.start(900)

        self._driver_worker = DriverInitWorker()
        self._driver_worker.success_signal.connect(self._on_driver_ready)
        self._driver_worker.error_signal.connect(self._on_driver_error)
        self._driver_worker.start()

    def _run_next_boot_step(self):
        if self._boot_index < len(self._boot_steps):
            self._boot_steps[self._boot_index]()
            self._boot_index += 1
        else:
            self._boot_timer.stop()
            self._check_if_boot_done()

    def _check_initializing(self):
        self.log_output.append("Initializing...")

    def _check_engine(self):
        import shutil
        if shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("chromedriver"):
            self.log_output.append("Loading engine... OK")
        else:
            self.log_output.append("Loading engine... OK (managed driver)")

    def _check_dependencies(self):
        missing = []
        for pkg in ["selenium", "bs4", "requests", "webdriver_manager"]:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        if missing:
            self.log_output.append(f"Checking dependencies... Missing: {', '.join(missing)}")
            self._boot_ok = False
        else:
            self.log_output.append("Checking dependencies... OK")

    def _check_setup(self):
        import tempfile, os
        try:
            tmp = tempfile.mktemp()
            with open(tmp, "w") as f:
                f.write("test")
            os.remove(tmp)
            self.log_output.append("Setting up... OK")
        except Exception:
            self.log_output.append("Setting up... Failed (disk write error)")
            self._boot_ok = False

    def _check_almost(self):
        self.log_output.append("Almost there...")

    def _on_driver_ready(self, driver):
        self.driver = driver
        self.start_button.setEnabled(True)
        self._driver_ready_pending = True
        self._check_if_boot_done()

    def _on_driver_error(self, error):
        self._boot_timer.stop()
        self.driver = None
        self.log_output.append("Could not start. Please check your internet connection and restart the app.")

    def _check_if_boot_done(self):
        if not self._boot_timer.isActive() and getattr(self, "_driver_ready_pending", False):
            self._driver_ready_pending = False
            self.log_output.clear()
            self.log_output.append("Ready!")

    def select_directory(self):
        directory = self.logic.select_directory()
        if directory:
            self.selected_dir_label.setText(directory)
            self.selected_dir_label.setStyleSheet(
                "color: #98989f; font-size: 12px; font-weight: 400; "
                "text-transform: none; letter-spacing: 0px; padding: 0px;"
            )
            self.selected_directory = directory

    def start_scraping(self):
        url = self.url_input.text().strip()
        directory_name = self.selected_directory

        if not self.logic.verify_input(url, directory_name):
            return
        if self.driver is None:
            self.log_output.append("WebDriver is not available. Cannot scrape.")
            return

        is_crawl = self._mode_group.checkedId() == 1

        if not is_crawl:
            max_pages = 1
            max_depth = 999
            self.log_output.append(f"Mode: Single Link | URL: {url}")
        else:
            if self.pages_selector.is_infinite():
                max_pages = INFINITE_PAGES
                max_depth = 999
                self.log_output.append(f"Mode: Crawling | Pages: Infinite | URL: {url}")
            else:
                pages = self.pages_selector.get_pages()
                if pages is None:
                    self.log_output.append("Please enter a valid number of pages.")
                    return
                max_pages = pages
                max_depth = 999
                self.log_output.append(f"Mode: Crawling | Pages: {max_pages} | URL: {url}")

        self._set_controls_enabled(False)
        self.start_button.setEnabled(False)
        self.start_button.setText("Scraping...")
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.worker = ScraperWorker(url, directory_name, self.driver, max_pages, max_depth)
        self.worker.log_signal.connect(self.log_output.append)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_scraping_finished)
        self.worker.start()

    def _on_progress(self, value):
        if self.pages_selector.is_infinite() and self._mode_group.checkedId() == 1:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)

    def _set_controls_enabled(self, val):
        self.mode_single.setEnabled(val)
        self.mode_crawl.setEnabled(val)
        self.pages_selector.set_enabled(val)

    def stop_scraping(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        self._on_scraping_finished(False)

    def _on_scraping_finished(self, success):
        self.start_button.setEnabled(True)
        self.start_button.setText("Start Scraping")
        self.stop_button.setEnabled(False)
        self._set_controls_enabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

    def _open_about(self):
        self._about_dialog = AboutDialog(self)
        self._about_dialog.show()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait()
        WebDriverManager.quit_driver()
        event.accept()


class AboutDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("About")
        self.setFixedSize(420, 400)
        self.setStyleSheet("background-color: #111113;")

        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().screenGeometry()
        self.move((screen.width() - 420) // 2, (screen.height() - 400) // 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(0)

        name_lbl = QLabel("DataScrape")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(
            "color: #e8e8ed; font-size: 22px; font-weight: 700; "
            "letter-spacing: -0.5px; text-transform: none; padding: 0px;"
        )
        layout.addWidget(name_lbl)
        layout.addSpacing(4)

        version_lbl = QLabel("Version 2.0")
        version_lbl.setAlignment(Qt.AlignCenter)
        version_lbl.setStyleSheet(
            "color: #48484a; font-size: 11px; font-weight: 500; "
            "text-transform: none; letter-spacing: 0.2px; padding: 0px;"
        )
        layout.addWidget(version_lbl)
        layout.addSpacing(14)

        desc_lbl = QLabel(
            "DataScrape is a powerful web scraping tool that\n"
            "extracts and saves web content locally."
        )
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setStyleSheet(
            "color: #98989f; font-size: 13px; font-weight: 400; "
            "text-transform: none; letter-spacing: 0px; padding: 0px; line-height: 1.5;"
        )
        layout.addWidget(desc_lbl)
        layout.addSpacing(20)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background: #2c2c2e; border: none; max-height: 1px;")
        layout.addWidget(div)
        layout.addSpacing(18)

        def make_badge(name, version, name_bg, ver_bg):
            pill = QWidget()
            pill.setStyleSheet("background: transparent;")
            pl = QHBoxLayout(pill)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.setSpacing(0)
            n = QLabel(name)
            n.setStyleSheet(
                f"background-color: {name_bg}; color: #ffffff; font-size: 11px; font-weight: 600; "
                f"border-top-left-radius: 5px; border-bottom-left-radius: 5px; "
                f"border-top-right-radius: 0px; border-bottom-right-radius: 0px; "
                f"padding: 4px 9px; text-transform: none; letter-spacing: 0.1px;"
            )
            v = QLabel(version)
            v.setStyleSheet(
                f"background-color: {ver_bg}; color: #ffffff; font-size: 11px; font-weight: 700; "
                f"border-top-left-radius: 0px; border-bottom-left-radius: 0px; "
                f"border-top-right-radius: 5px; border-bottom-right-radius: 5px; "
                f"padding: 4px 9px; text-transform: none; letter-spacing: 0.1px;"
            )
            pl.addWidget(n)
            pl.addWidget(v)
            return pill

        row1 = QHBoxLayout()
        row1.setAlignment(Qt.AlignCenter)
        row1.setSpacing(8)
        row1.addWidget(make_badge("Python", "3.12", "#3572A5", "#4584b6"))
        row1.addWidget(make_badge("PyQt5",  "5.15", "#21522e", "#41cd52"))
        layout.addLayout(row1)
        layout.addSpacing(8)

        row2 = QHBoxLayout()
        row2.setAlignment(Qt.AlignCenter)
        row2.addWidget(make_badge("Selenium", "4.0", "#1a3d1a", "#43b02a"))
        layout.addLayout(row2)
        layout.addSpacing(18)

        author_lbl = QLabel('Developed by <a href="https://andresnicolas.com" style="color:#0a84ff; text-decoration:none;">Andres Nicolas</a>')
        author_lbl.setAlignment(Qt.AlignCenter)
        author_lbl.setOpenExternalLinks(True)
        author_lbl.setStyleSheet(
            "color: #636366; font-size: 12px; font-weight: 400; "
            "text-transform: none; letter-spacing: 0px; padding: 0px;"
        )
        layout.addWidget(author_lbl)

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