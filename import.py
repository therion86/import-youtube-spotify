import sys
import subprocess
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QMessageBox, QWidget
import os

class ImportWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Import auswählen")
        self.setGeometry(100, 100, 400, 200)

        # Layout und Buttons
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        # Buttons zum Auswahl der Importoption
        spotify_button = QPushButton("Spotify Import", self)
        spotify_button.clicked.connect(self.import_spotify)
        layout.addWidget(spotify_button)

        youtube_button = QPushButton("YouTube Import", self)
        youtube_button.clicked.connect(self.import_youtube)
        layout.addWidget(youtube_button)

        central_widget.setLayout(layout)

    def import_spotify(self):
        """Startet die Spotify-Importfunktion."""
        try:
            # Relativer Pfad zu spotify.py
            script_path = os.path.join(os.path.dirname(__file__), 'spotify.py')
            subprocess.run([sys.executable, script_path], check=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Starten von Spotify: {e}")

    def import_youtube(self):
        """Startet die YouTube-Importfunktion."""
        try:
            # Relativer Pfad zu youtube.py
            script_path = os.path.join(os.path.dirname(__file__), 'youtube.py')
            subprocess.run([sys.executable, script_path], check=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Starten von YouTube: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImportWindow()
    window.show()
    sys.exit(app.exec_())
