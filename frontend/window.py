from PyQt5.QtWidgets import QMainWindow, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget, QFileDialog
from backend.extractor import runExtractor
import os

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
        self.dir_button.clicked.connect(self.select_directory)
        layout.addWidget(self.dir_button)

        self.selected_dir_label = QLabel("No directory selected", self)
        layout.addWidget(self.selected_dir_label)

        self.start_button = QPushButton("Start Scraping")
        self.start_button.clicked.connect(self.start_scraping)
        layout.addWidget(self.start_button)

        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.selected_directory = None

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.selected_dir_label.setText(f"Selected Directory: {directory}")
            self.selected_directory = directory

    def start_scraping(self):
        url = self.url_input.text().strip()
        directory_name = self.selected_directory

        if not directory_name:
            self.log_output.append("No directory selected. Please select a directory before starting.")
            return

        self.log_output.append(f"Starting scraping for URL: {url}")
        try:
            extractor = runExtractor(url, directory_name)
            result = extractor.extract_link(url)
            if result:
                self.log_output.append("Scraping completed successfully.")
            else:
                self.log_output.append("Scraping finished with no data.")
        except Exception as e:
            self.log_output.append(f"Error: {str(e)}")
