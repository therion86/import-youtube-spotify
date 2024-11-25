import sys
import json
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QFileDialog,
    QListWidget, QInputDialog, QComboBox, QMessageBox, QDialog, QLabel, QDialogButtonBox, QWidget, QTextEdit, QListWidgetItem, QLineEdit
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import requests  # Hier wird requests importiert
from google.auth.transport.requests import Request
import time  # Wir verwenden time.sleep, um Verzögerungen zwischen den Anfragen einzubauen

# Lade Konfigurationsdaten aus youtube.json (OAuth2 JSON)
def load_youtube_config():
    try:
        with open("youtube.json", "r") as config_file:
            config = json.load(config_file)
            return config  # Gibt die gesamte Konfiguration zurück
    except FileNotFoundError:
        print("Fehler: Die Datei 'youtube.json' wurde nicht gefunden.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Fehler: Die Datei 'youtube.json' enthält ungültiges JSON.")
        sys.exit(1)

# Authentifizierung und Erstellen des YouTube API-Clients
def authenticate_youtube(config):
    client_secrets_file = "youtube.json"  # Das OAuth2 JSON von YouTube

    # OAuth2-Flow initialisieren
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
    )

    # Authentifizierung durchführen
    credentials = flow.run_local_server(port=0)

    # YouTube API-Client erstellen
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )

    return youtube, credentials

# Manuelle Suche für YouTube
class SearchWizard(QDialog):
    """Dialog zur manuellen Suche nach YouTube-Videos."""
    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manuelle Videosuche")
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

# Dialog zur Auswahl eines YouTube-Videos
class VideoWizard(QDialog):
    """Dialog zur Auswahl von YouTube-Suchergebnissen mit Thumbnail."""
    def __init__(self, video, search_results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video auswählen")
        self.selected_video_id = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Video: {video}"))

        self.result_list = QListWidget(self)
        self.result_list.setSelectionMode(QListWidget.SingleSelection)

        # Füge alle Ergebnisse als Listeneinträge hinzu
        self.search_results = search_results  # Speichern der Suchergebnisse
        for result in search_results:
            item = QListWidgetItem(f"{result['snippet']['title']}")
            thumbnail_url = result['snippet']['thumbnails']['high']['url'] if result['snippet']['thumbnails'] else None
            if thumbnail_url:
                response = requests.get(thumbnail_url)
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                thumbnail_label = QLabel(self)
                thumbnail_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio))
                item.setIcon(QIcon(pixmap))
            self.result_list.addItem(item)

        layout.addWidget(self.result_list)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        """Wählt das angeklickte Video aus und gibt die Video-ID zurück."""
        selected_item = self.result_list.currentItem()
        if selected_item:
            index = self.result_list.row(selected_item)
            self.selected_video_id = self.search_results[index]['id']['videoId']
        super().accept()

# Hauptfenster für den Import
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Playlist Manager")
        self.setGeometry(100, 100, 600, 400)

        self.song_data = None
        self.skipped_songs = []  # Liste für übersprungene Titel

        # Zentrales Widget erstellen
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        self.song_list_widget = QListWidget(self)
        layout.addWidget(self.song_list_widget)

        load_button = QPushButton("Excel-Datei laden")
        load_button.clicked.connect(self.load_excel)
        layout.addWidget(load_button)

        youtube_button = QPushButton("Zu YouTube hinzufügen")
        youtube_button.clicked.connect(self.add_to_youtube)
        layout.addWidget(youtube_button)

        # Layout dem zentralen Widget zuweisen
        central_widget.setLayout(layout)

    def load_excel(self):
        """Lädt eine Excel-Datei und zeigt die Songs an."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Excel-Datei auswählen", "", "Excel Files (*.xlsx *.xls)")
        if not file_name:
            return

        try:
            self.song_data = pd.read_excel(file_name, header=None, engine='openpyxl')
            self.song_list_widget.clear()
            for _, row in self.song_data.iterrows():
                artist, title = row[0], row[1]
                self.song_list_widget.addItem(f"{artist} - {title}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Laden der Excel-Datei: {e}")

    def add_to_youtube(self):
        """Fügt die Songs zu YouTube hinzu."""
        if self.song_data is None:
            QMessageBox.warning(self, "Warnung", "Keine Excel-Datei geladen.")
            return

        playlist_name, ok = QInputDialog.getText(self, "Playlist erstellen", "Name der Playlist:")
        if not ok or not playlist_name:
            return

        # Konfiguration laden und YouTube-Client erstellen
        config = load_youtube_config()
        youtube, credentials = authenticate_youtube(config)

        try:
            # YouTube Playlist erstellen
            playlist_request = youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": playlist_name,
                        "description": "Eine Playlist mit deinen Lieblingssongs",
                    },
                    "status": {
                        "privacyStatus": "public"
                    }
                }
            )
            playlist_response = playlist_request.execute()
            playlist_id = playlist_response["id"]
            print(f"Playlist '{playlist_name}' erfolgreich erstellt.")

            # Songs zur Playlist hinzufügen
            for _, row in self.song_data.iterrows():
                artist, title = row[0], row[1]
                query = f"{artist} {title}"

                while True:
                    # Wenn die Session abgelaufen ist, Token erneuern
                    if credentials and credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())  # Token erneuern

                    search_results = youtube.search().list(
                        part="snippet",
                        q=query,
                        type="video",
                        maxResults=5
                    ).execute()

                    if not search_results['items']:
                        self.skipped_songs.append(query)
                        break

                    wizard = VideoWizard(f"{artist} - {title}", search_results['items'], self)
                    if wizard.exec_() == QDialog.Accepted and wizard.selected_video_id:
                        video_id = wizard.selected_video_id
                        self.add_video_to_playlist(youtube, playlist_id, video_id)
                        break
                    else:
                        manual_search = QMessageBox.question(
                            self, "Song übersprungen",
                            "Kein passendes Video gefunden. Möchtest du erneut suchen?",
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
            QMessageBox.critical(self, "Fehler", f"Fehler bei der YouTube-Integration: {e}")

    def show_skipped_songs(self):
        """Zeigt übersprungene Songs in einem Dialog an."""
        if not self.skipped_songs:
            QMessageBox.information(self, "Info", "Keine Songs wurden übersprungen.")
            return

        skipped_dialog = QDialog(self)
        skipped_dialog.setWindowTitle("Übersprungene Songs")
        layout = QVBoxLayout(skipped_dialog)

        skipped_songs_text = ", ".join(self.skipped_songs)

        text_edit = QTextEdit(skipped_dialog)
        text_edit.setPlainText(skipped_songs_text)  # Alle Songs als eine einzelne, komma-separierte Liste
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok, skipped_dialog)
        button_box.accepted.connect(skipped_dialog.accept)
        layout.addWidget(button_box)

        skipped_dialog.exec_()

    def add_video_to_playlist(self, youtube, playlist_id, video_id):
        """Füge das Video zu einer Playlist hinzu."""
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        ).execute()

# Hauptanwendung starten
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
