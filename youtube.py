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
import requests
from google.auth.transport.requests import Request
import time

def load_youtube_config():
    try:
        with open("youtube.json", "r") as config_file:
            config = json.load(config_file)
            return config
    except FileNotFoundError:
        print("Error: youtube.json not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: youtube.json has no valid JSON.")
        sys.exit(1)

def authenticate_youtube(config):
    client_secrets_file = "youtube.json"

    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
    )

    credentials = flow.run_local_server(port=0)

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )

    return youtube, credentials

class SearchWizard(QDialog):
    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual video search")
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

class VideoWizard(QDialog):
    def __init__(self, video, search_results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select video")
        self.selected_video_id = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Video: {video}"))

        self.result_list = QListWidget(self)
        self.result_list.setSelectionMode(QListWidget.SingleSelection)

        self.search_results = search_results
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
        selected_item = self.result_list.currentItem()
        if selected_item:
            index = self.result_list.row(selected_item)
            self.selected_video_id = self.search_results[index]['id']['videoId']
        super().accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Playlist Manager")
        self.setGeometry(100, 100, 600, 400)

        self.song_data = None
        self.skipped_songs = [] 

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        self.song_list_widget = QListWidget(self)
        layout.addWidget(self.song_list_widget)

        load_button = QPushButton("Load excel file")
        load_button.clicked.connect(self.load_excel)
        layout.addWidget(load_button)

        youtube_button = QPushButton("Add to youtube")
        youtube_button.clicked.connect(self.add_to_youtube)
        layout.addWidget(youtube_button)

        central_widget.setLayout(layout)

    def load_excel(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select excel file", "", "Excel Files (*.xlsx *.xls)")
        if not file_name:
            return

        try:
            self.song_data = pd.read_excel(file_name, header=None, engine='openpyxl')
            self.song_list_widget.clear()
            for _, row in self.song_data.iterrows():
                artist, title = row[0], row[1]
                self.song_list_widget.addItem(f"{artist} - {title}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error while loading excel file: {e}")

    def add_to_youtube(self):
        if self.song_data is None:
            QMessageBox.warning(self, "Warning", "No excel file loaded.")
            return

        playlist_name, ok = QInputDialog.getText(self, "Create playlist", "Name of playlist:")
        if not ok or not playlist_name:
            return
        
        playlist_description, ok = QInputDialog.getText(self, "Playlist descrpiton", "Description of playlist:")
        if not ok or not playlist_description:
            return

        config = load_youtube_config()
        youtube, credentials = authenticate_youtube(config)

        try:
            playlist_request = youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": playlist_name,
                        "description": playlist_description,
                    },
                    "status": {
                        "privacyStatus": "public"
                    }
                }
            )
            playlist_response = playlist_request.execute()
            playlist_id = playlist_response["id"]
            print(f"Playlist '{playlist_name}' created successful.")

            for _, row in self.song_data.iterrows():
                artist, title = row[0], row[1]
                query = f"{artist} {title}"

                while True:
                    if credentials and credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())

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
                            self, "Song skipped",
                            "No valid video found. Do you want to search again?",
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

            QMessageBox.information(self, "Success", f"Playlist '{playlist_name}' successful created.")
            self.show_skipped_songs()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error with youtube integration: {e}")

    def show_skipped_songs(self):
        if not self.skipped_songs:
            QMessageBox.information(self, "Info", "No songs where skipped.")
            return

        skipped_dialog = QDialog(self)
        skipped_dialog.setWindowTitle("Skipped Songs")
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

    def add_video_to_playlist(self, youtube, playlist_id, video_id):
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
