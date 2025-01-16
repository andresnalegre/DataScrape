import os
import re
from PyQt5.QtWidgets import QFileDialog

class UiLogic:
    def __init__(self, log_output, parent):
        self.log_output = log_output
        self.parent = parent

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self.parent, "Select Directory")
        if directory:
            return directory
        return None

    def is_valid_url(self, url):
        regex = re.compile(
            r'^(?:(?:http|https|ftp)://)?'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
            r'localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'
            r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'
            r'(?::\d+)?(?:/?|[/?]\S+)?$', re.IGNORECASE)
        return re.match(regex, url) is not None

    def verify_input(self, url, directory_name):
        if not url:
            self.log_output.append("Please provide a URL.")
            return False
        elif not self.is_valid_url(url):
            self.log_output.append("The URL is not valid.")
            return False
        elif not directory_name:
            self.log_output.append("Please select a directory to save.")
            return False
        elif not os.path.isdir(directory_name):
            self.log_output.append("The directory is not valid.")
            return False
        return True
