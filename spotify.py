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



def load_spotify_config():
    try:
        with open("spotify.json", "r") as config_file:
            config = json.load(config_file)
            return config
    except FileNotFoundError:
        print("spotify.json not found!")
        sys.exit(1)
    except json.JSONDecodeError:
        print("spotify.json is no well-formed json!")
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
    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual Songsearch")
        self.updated_query = query

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Query: {query}"))

        self.query_input = QLineEdit(self)
        self.query_input.setText(query)
        layout.addWidget(self.query_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        self.updated_query = self.query_input.text()
        super().accept()


class SongWizard(QDialog):
    def __init__(self, song, search_results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Song")
        self.selected_uri = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Song: {song}"))

        self.result_list = QListWidget(self)
        self.result_list.setSelectionMode(QListWidget.SingleSelection)

        self.search_results = search_results
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
        self.skipped_songs = []

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.song_table_widget = QTableWidget(self)
        self.song_table_widget.setColumnCount(2)
        self.song_table_widget.setHorizontalHeaderLabels(["Interpret", "Titel"])
        self.song_table_widget.setColumnWidth(0,300)
        self.song_table_widget.setColumnWidth(1,400)
        layout.addWidget(self.song_table_widget)

        load_button = QPushButton("Import Excel")
        load_button.clicked.connect(self.load_excel)
        layout.addWidget(load_button)

        spotify_button = QPushButton("Add to Spotify")
        spotify_button.clicked.connect(self.add_to_spotify)
        layout.addWidget(spotify_button)

        central_widget.setLayout(layout)

    def load_excel(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Choose File", "", "Excel Files (*.xlsx *.xls)")
        if not file_name:
            return

        try:
            self.song_data = pd.read_excel(file_name, header=None, engine='openpyxl')
            
            self.song_table_widget.setRowCount(len(self.song_data))

            for row_idx, row in self.song_data.iterrows():
                artist, title = row[0], row[1]
                self.song_table_widget.setItem(row_idx, 0, QTableWidgetItem(artist))
                self.song_table_widget.setItem(row_idx, 1, QTableWidgetItem(title))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error while loading excel file: {e}")

    def add_to_spotify(self):
        if self.song_data is None:
            QMessageBox.warning(self, "Warning", "No excel file was loaded")
            return

        playlist_name, ok = QInputDialog.getText(self, "Create playlist", "Name of playlist:")
        if not ok or not playlist_name:
            return

        try:
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
                                self, "Song skipped",
                                "No matching song found. Do you want to search again?",
                                QMessageBox.Yes | QMessageBox.No
                            )
                            if manual_search == QMessageBox.No:
                                self.skipped_songs.append(query)
                                break
                            search_dialog = SearchWizard(query, self)
                            if search_dialog.exec_() == QDialog.Accepted:
                                query = search_dialog.updated_query
                            else:
                                self.skipped_songs.append(query)
                                break

            QMessageBox.information(self, "Success", f"Playlist '{playlist_name}' was created.")
            self.show_skipped_songs()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error with spotify integration: {e}")

    def show_skipped_songs(self):
        if not self.skipped_songs:
            QMessageBox.information(self, "Info", "No songs where skipped.")
            return

        skipped_dialog = QDialog(self)
        skipped_dialog.setWindowTitle("Skipped songs")
        layout = QVBoxLayout(skipped_dialog)

        skipped_songs_text = ", ".join(self.skipped_songs)

        text_edit = QTextEdit(skipped_dialog)
        text_edit.setPlainText(skipped_songs_text)
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
