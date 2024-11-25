# Youtube and/or Spotify Importer from Excelfile

for spotify you need a spotify.json with following content:
```
  {
    "client_id":"YOUR CLIENT ID",
    "client_secret":"YOUR CLIENT ID",
    "redirect_uri":"http://localhost:8080", #set in the py
    "scope":"playlist-modify-public" 
}
```

for youtube you need to import your secret.json from youtube api an rename it to youtube.json
