from asyncio import create_subprocess_exec, to_thread
from discord import FFmpegOpusAudio
from pytube import Playlist, YouTube
from asyncio.subprocess import PIPE
from mutagen.easyid3 import EasyID3
from aiofiles import os, open
from mutagen.mp3 import MP3
from time import time
from random import choice
import os as base_os
import sys

executable_folder = base_os.path.dirname(base_os.path.realpath(__file__))

async def is_downloaded(song: str) -> bool:
    return await os.path.exists(f"songs/{song}.mp3")

async def download(id: str):
    if await is_downloaded(id): return
    print(f"Downloading {id}", file=sys.stderr)
    process = await create_subprocess_exec("python", executable_folder + "/download.py", id, stdout=PIPE, stderr=PIPE)
    code = await process.wait()
    if code != 0:
        message = (await process.stderr.read()).decode("utf-8") # type: ignore
        raise Exception(f"Failed to download {id}:\n{message.strip()}")

async def update(should_stop: list[bool]):
    member_songs: set[str] = set()
    for member in await os.listdir("members"):
        member_songs.update(await os.listdir(f"members/{member}"))
    downloaded_songs = {song.split(".")[0] for song in await os.listdir("songs")}
    
    # Download songs that are not downloaded
    for song in member_songs.difference(downloaded_songs):
        if should_stop[0]: break
        try: await download(song)
        except Exception as e: print(e, file=sys.stderr)

async def next_song(members: set[str]) -> str | None:
    if members: print(f"Finding next song for {members}", file=sys.stderr)
    member_songs: set[str] = set()
    for member in members:
        if not await os.path.exists(f"members/{member}"): continue
        member_songs.update(await os.listdir(f"members/{member}"))
    if len(member_songs) == 0: return None
    downloaded_songs = {song.split(".")[0] for song in await os.listdir("songs")}
    possible_songs = member_songs.intersection(downloaded_songs)
    if len(possible_songs) == 0: return None
    return choice(list(possible_songs))

async def load_song(song: str) -> FFmpegOpusAudio:
    print(f"Opening {song} with ffmpeg", file=sys.stderr)
    source = FFmpegOpusAudio(f"songs/{song}.mp3")
    await to_thread(source.read)
    return source

async def resolve_query(query: str) -> list[str]:
    print(f"Resolving {query}", file=sys.stderr)
    try:
        if "list=" in query:
            def _internal_playlist(query: str) -> list[str]:
                return list(video.video_id for video in Playlist(query).videos)
            return await to_thread(_internal_playlist, query)
        elif "v=" in query:
            return [query.split("v=")[1].split("&")[0]]
        elif "youtu.be" in query:
            return [query.split("youtu.be/")[1].split("?")[0]]
        elif len(query) == 11:
            return [query]
        def _internal_youtube(query: str) -> list[str]:
            return [YouTube(query).video_id]
        return await to_thread(_internal_youtube, query)
    except:
        return []

async def load_song_data(song: str) -> dict:
    print(f"Loading {song} metadata", file=sys.stderr)
    if not await is_downloaded(song): await download(song)
    audio = await to_thread(MP3, f"songs/{song}.mp3", ID3=EasyID3)
    return {
        "title": audio["title"][0] if "title" in audio else "Unknown",
        "artist": audio["artist"][0] if "artist" in audio else "Unknown",
        "thumbnail_url": f"https://img.youtube.com/vi/{song}/hqdefault.jpg",
        "duration": round(audio.info.length),
    }

async def add_to_member(member: str, song: str) -> bool:
    if await os.path.exists(f"members/{member}/{song}"): return False
    print(f"Adding {song} to {member}", file=sys.stderr)
    if not await os.path.exists(f"members/{member}"): await os.mkdir(f"members/{member}")
    async with open(f"members/{member}/{song}", "w") as f:
        await f.flush()
    return True

async def remove_from_member(member: str, song: str) -> bool:
    if await os.path.exists(f"members/{member}/{song}"):
        print(f"Removing {song} from {member}", file=sys.stderr)
        await os.remove(f"members/{member}/{song}")
        for member in await os.listdir("members"):
            if await os.path.exists(f"members/{member}/{song}"): break
        else: await os.remove(f"songs/{song}.mp3")
        return True
    return False