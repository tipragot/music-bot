import subprocess
from uuid import uuid4
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from pytube import YouTube
from pydub import AudioSegment
import sys, os

# Get id from parameters
id = sys.argv[1]
download_id = uuid4().hex

try:
    # Check for correct audio duration
    video = YouTube(f"https://youtube.com/watch?v={id}")
    if video.length > 600: raise Exception("audio too long")

    # Downloading the audio
    code = subprocess.call([
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        f"https://youtube.com/watch?v={id}",
        "-o", f"temp_{download_id}.%(ext)s",
    ])
    if code != 0: raise Exception(f"failed to download {id}: {code}")

    # Normalize the audio
    sound = AudioSegment.from_file(f"temp_{download_id}.mp3", "mp3")
    normalized_sound = sound.apply_gain(-20.0 - sound.dBFS)
    normalized_sound.export(f"temp_{download_id}.mp3", format="mp3")

    # Add metadata
    audio = MP3(f"temp_{download_id}.mp3", ID3=EasyID3)
    audio["title"] = video.title
    audio["artist"] = video.author
    audio.save()

    # Rename the file
    if not os.path.exists("songs"): os.mkdir("songs")
    os.rename(f"temp_{download_id}.mp3", f"songs/{id}.mp3")
except Exception as e:
    if os.path.exists(f"temp_{download_id}.webm"): os.remove(f"temp_{download_id}.webm")
    if os.path.exists(f"temp_{download_id}.mp3"): os.remove(f"temp_{download_id}.mp3")
    raise e