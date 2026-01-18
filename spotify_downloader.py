from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import requests
import os
import tempfile
import urllib.parse

app = FastAPI()

@app.get("/download")
def download_spotify_track(spotify_url: str):
    """
    Download Spotify track from SpotDown and send to user browser
    """
    # Session
    session = requests.Session()
    session.get("https://spotdown.org", headers={"User-Agent": "Mozilla/5.0"})

    # Download API
    download_api = "https://spotdown.org/api/download"
    payload = {"url": spotify_url}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://spotdown.org/",
        "Origin": "https://spotdown.org",
        "Content-Type": "application/json"
    }

    response = session.post(download_api, json=payload, headers=headers, stream=True)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Download failed")

    # Dynamic filename using Spotify track ID
    parsed = urllib.parse.urlparse(spotify_url)
    track_id = parsed.path.split("/")[-1]  # e.g., 2GzjIHQ87BF2zgbmmthZzO
    filename = f"{track_id}.mp3"

    # Save to temp file
    fd, temp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    with open(temp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    # Send file to browser
    resp = FileResponse(temp_path, media_type="audio/mpeg", filename=filename)

    # Cleanup after sending
    def remove_file(sender):
        try:
            os.remove(temp_path)
        except:
            pass
    resp.background = remove_file

    return resp
