from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import requests, tempfile, os, re, zipfile

app = FastAPI(title="Spotify Track & Playlist Downloader")

# ---------------- helpers ----------------
def clean_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def is_playlist(url: str) -> bool:
    return "playlist" in url.lower()

def get_oembed(url: str):
    r = requests.get("https://open.spotify.com/oembed", params={"url": url}, timeout=15)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid Spotify URL")
    return r.json()

def spotdown_download(session, spotify_url, save_path):
    r = session.post(
        "https://spotdown.org/api/download",
        json={"url": spotify_url},
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://spotdown.org/",
            "Origin": "https://spotdown.org",
            "Content-Type": "application/json"
        },
        stream=True,
        timeout=60
    )
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Download failed")

    with open(save_path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

# ---------------- API: INFO ----------------
@app.get("/info")
def song_or_playlist_info(spotify_url: str):
    data = get_oembed(spotify_url)

    return {
        "type": "playlist" if is_playlist(spotify_url) else "track",
        "title": data.get("title"),
        "author": data.get("author_name"),
        "thumbnail": data.get("thumbnail_url"),
        "duration": "Unknown"
    }

# ---------------- API: DOWNLOAD ----------------
@app.get("/download")
def download(spotify_url: str):

    session = requests.Session()
    session.get("https://spotdown.org", headers={"User-Agent": "Mozilla/5.0"})

    # -------- TRACK --------
    if not is_playlist(spotify_url):
        info = get_oembed(spotify_url)
        filename = clean_filename(info.get("title", "spotify_track")) + ".mp3"

        fd, temp_mp3 = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        spotdown_download(session, spotify_url, temp_mp3)

        return FileResponse(
            temp_mp3,
            filename=filename,
            media_type="audio/mpeg"
        )

    # -------- PLAYLIST --------
    playlist_data = get_oembed(spotify_url)
    playlist_name = clean_filename(playlist_data.get("title", "spotify_playlist"))

    tracks_api = f"https://spotdown.org/api/playlist?url={spotify_url}"
    r = session.get(tracks_api, timeout=30)

    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Playlist fetch failed")

    tracks = r.json().get("tracks", [])
    if not tracks:
        raise HTTPException(status_code=500, detail="No tracks found")

    zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(zip_fd)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for track in tracks:
            track_url = track.get("url")
            track_name = clean_filename(track.get("title", "track")) + ".mp3"

            fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

            spotdown_download(session, track_url, mp3_path)
            zipf.write(mp3_path, track_name)
            os.remove(mp3_path)

    return FileResponse(
        zip_path,
        filename=f"{playlist_name}.zip",
        media_type="application/zip"
    )
