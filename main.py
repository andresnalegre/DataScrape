import sys
import os
import logging
import signal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from frontend.window import MainWindow
from backend.webdriver import WebDriverManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def apply_stylesheet(app):
    stylesheet_path = os.path.join(os.path.dirname(__file__), 'frontend', 'styles.qss')
    with open(stylesheet_path, 'r') as file:
        app.setStyleSheet(file.read())

def handle_signal(sig, frame):
    logging.info("Interrupt signal received! Shutting down WebDriver and application...")
    WebDriverManager.quit_driver()
    QApplication.quit()

def main():
    signal.signal(signal.SIGINT, handle_signal)

    app = QApplication(sys.argv)
    apply_stylesheet(app)

    window = MainWindow()
    window.show()

    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    try:
        sys.exit(app.exec_())
    except Exception as e:
        logging.error(f"Error during application execution: {e}")
    finally:
        logging.info("Shutting down WebDriver...")
        WebDriverManager.quit_driver()

if __name__ == "__main__":
    main()
