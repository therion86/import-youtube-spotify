import sys
import json
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QInputDialog, QMessageBox, QDialog, QLabel, QDialogButtonBox, QWidget, QLineEdit, QTextEdit, QListWidget, QListWidgetItem
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth


# Lade Konfigurationsdaten aus spotify.json
def load_spotify_config():
    try:
        with open("spotify.json", "r") as config_file:
            config = json.load(config_file)
            return config
    except FileNotFoundError:
        print("Fehler: Die Datei 'spotify.json' wurde nicht gefunden.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Fehler: Die Datei 'spotify.json' enthält ungültiges JSON.")
        sys.exit(1)


config = load_spotify_config()

# Spotify-Authentifizierung
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=config["client_id"],
    client_secret=config["client_secret"],
    redirect_uri=config["redirect_uri"],
    scope=config["scope"]
))


class SearchWizard(QDialog):
    """Dialog zur manuellen Songsuche."""
    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manuelle Songsuche")
        self.updated_query = query

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Suchbegriff: {query}"))

        self.query_input = QLineEdit(self)
        self.query_input.setText(query)  # Setze den initialen Text
        layout.addWidget(self.query_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        """Speichert den aktualisierten Suchbegriff."""
        self.updated_query = self.query_input.text()
        super().accept()


class SongWizard(QDialog):
    """Dialog zur Auswahl von Spotify-Suchergebnissen mit Albumcover."""
    def __init__(self, song, search_results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Song auswählen")
        self.selected_uri = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Song: {song}"))

        self.result_list = QListWidget(self)
        self.result_list.setSelectionMode(QListWidget.SingleSelection)

        # Füge alle Ergebnisse als Listeneinträge hinzu
        self.search_results = search_results  # Speichern der Suchergebnisse
        for result in search_results:
            item = QListWidgetItem(f"{result['name']} - {', '.join(artist['name'] for artist in result['artists'])}")
            album_cover_url = result['album']['images'][1]['url'] if result['album']['images'] else None
            if album_cover_url:
                response = requests.get(album_cover_url)
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                album_cover_label = QLabel(self)
                album_cover_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio))
                item.setIcon(QIcon(pixmap))
            self.result_list.addItem(item)

        layout.addWidget(self.result_list)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        """Wählt das angeklickte Element aus und gibt den URI zurück."""
        selected_item = self.result_list.currentItem()
        if selected_item:
            index = self.result_list.row(selected_item)
            self.selected_uri = self.search_results[index]['uri']
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Playlist Manager")
        self.setGeometry(100, 100, 600, 400)

        self.song_data = None
        self.skipped_songs = []  # Liste für übersprungene Titel

        # Zentrales Widget erstellen
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        # Erstelle eine QTableWidget für die Anzeige der Songs
        self.song_table_widget = QTableWidget(self)
        self.song_table_widget.setColumnCount(2)  # Zwei Spalten: Interpret und Titel
        self.song_table_widget.setHorizontalHeaderLabels(["Interpret", "Titel"])
        layout.addWidget(self.song_table_widget)

        load_button = QPushButton("Excel-Datei laden")
        load_button.clicked.connect(self.load_excel)
        layout.addWidget(load_button)

        spotify_button = QPushButton("Zu Spotify hinzufügen")
        spotify_button.clicked.connect(self.add_to_spotify)
        layout.addWidget(spotify_button)

        # Layout dem zentralen Widget zuweisen
        central_widget.setLayout(layout)

    def load_excel(self):
        """Lädt eine Excel-Datei und zeigt die Songs in einer Tabelle an."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Excel-Datei auswählen", "", "Excel Files (*.xlsx *.xls)")
        if not file_name:
            return

        try:
            self.song_data = pd.read_excel(file_name, header=None, engine='openpyxl')
            
            # Setze die Zeilenanzahl der Tabelle basierend auf der Anzahl der Zeilen in der Excel-Datei
            self.song_table_widget.setRowCount(len(self.song_data))

            for row_idx, row in self.song_data.iterrows():
                artist, title = row[0], row[1]
                # Füge die Daten in die Tabelle ein
                self.song_table_widget.setItem(row_idx, 0, QTableWidgetItem(artist))
                self.song_table_widget.setItem(row_idx, 1, QTableWidgetItem(title))

        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Laden der Excel-Datei: {e}")

    def add_to_spotify(self):
        """Fügt die Songs zu Spotify hinzu."""
        if self.song_data is None:
            QMessageBox.warning(self, "Warnung", "Keine Excel-Datei geladen.")
            return

        playlist_name, ok = QInputDialog.getText(self, "Playlist erstellen", "Name der Playlist:")
        if not ok or not playlist_name:
            return

        try:
            # Playlist bei Spotify erstellen
            playlist = sp.user_playlist_create(sp.me()['id'], playlist_name)
            playlist_id = playlist['id']

            for row_idx in range(self.song_table_widget.rowCount()):
                artist_item = self.song_table_widget.item(row_idx, 0)
                title_item = self.song_table_widget.item(row_idx, 1)
                
                if artist_item and title_item:
                    artist = artist_item.text()
                    title = title_item.text()
                    query = f"{artist} {title}"

                    while True:
                        search_results = sp.search(query, type='track', limit=5, market='DE')

                        if not search_results['tracks']['items']:
                            self.skipped_songs.append(query)
                            break

                        wizard = SongWizard(f"{artist} - {title}", search_results['tracks']['items'], self)
                        if wizard.exec_() == QDialog.Accepted and wizard.selected_uri:
                            sp.playlist_add_items(playlist_id, [wizard.selected_uri])
                            break
                        else:
                            manual_search = QMessageBox.question(
                                self, "Song übersprungen",
                                "Kein passender Song gefunden. Möchtest du erneut suchen?",
                                QMessageBox.Yes | QMessageBox.No
                            )
                            if manual_search == QMessageBox.No:
                                self.skipped_songs.append(query)
                                break
                            search_dialog = SearchWizard(query, self)
                            if search_dialog.exec_() == QDialog.Accepted:
                                query = search_dialog.updated_query  # Aktualisiert den Suchbegriff
                            else:
                                self.skipped_songs.append(query)
                                break

            QMessageBox.information(self, "Erfolg", f"Playlist '{playlist_name}' wurde erfolgreich erstellt.")
            self.show_skipped_songs()

        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler bei der Spotify-Integration: {e}")

    def show_skipped_songs(self):
        """Zeigt übersprungene Songs in einem Dialog an, als komma-separierte Liste."""
        if not self.skipped_songs:
            QMessageBox.information(self, "Info", "Keine Songs wurden übersprungen.")
            return

        skipped_dialog = QDialog(self)
        skipped_dialog.setWindowTitle("Übersprungene Songs")
        layout = QVBoxLayout(skipped_dialog)

        # Komma-separierte Liste der übersprungenen Songs
        skipped_songs_text = ", ".join(self.skipped_songs)

        text_edit = QTextEdit(skipped_dialog)
        text_edit.setPlainText(skipped_songs_text)  # Alle Songs als eine einzelne, komma-separierte Liste
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok, skipped_dialog)
        button_box.accepted.connect(skipped_dialog.accept)
        layout.addWidget(button_box)

        skipped_dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
