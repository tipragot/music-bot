from asyncio.subprocess import PIPE
import sys
from discord import Client, Color, Embed, Intents, Member, Message, Reaction, TextChannel, VoiceChannel, VoiceClient, VoiceProtocol
from songs import add_to_member, download, is_downloaded, load_song, load_song_data, next_song, remove_from_member, resolve_query, update
from asyncio import create_subprocess_exec
from signal import SIGTERM
from asyncio import sleep
from os import environ
from random import randint
from datetime import datetime
import os
import logging

executable_folder = os.path.dirname(os.path.realpath(__file__))

client = Client(intents=Intents.all())
playlist: list[tuple[Message, str]] = []
should_stop = False
skip_count = 0

async def send_generated_message(channel: TextChannel):
    print("Generating a new message...", file=sys.stderr)
    process = await create_subprocess_exec("python", executable_folder + "/generate.py", stdout=PIPE, stderr=PIPE)
    stdout, _ = await process.communicate()
    await channel.send(stdout.decode('utf-8').strip())

def stop_signal_handler():
    global should_stop
    print("Received SIGTERM signal", file=sys.stderr)
    should_stop = True

@client.event
async def on_ready():
    client.loop.add_signal_handler(SIGTERM, stop_signal_handler)
    update_should_stop = [False]
    update_task = client.loop.create_task(update(update_should_stop))

    # Load the channels
    text_channel: TextChannel = client.get_channel(1210446807046430770) # type: ignore
    voice_channel: VoiceChannel = client.get_channel(1089267667065647165) # type: ignore

    # Clear all messages in the text channel
    await text_channel.purge(limit=None)

    # Create the status message
    status_message = await text_channel.send(embed=Embed(title="Ready to play music!"))

    # While the bot should run
    while not should_stop:
        try:
            current_hour = datetime.now().hour
            if current_hour >= 8 and randint(0, 1000) == 0:
                await send_generated_message(client.get_channel(848555343054110721))
            await play_next_song(status_message, voice_channel)
        except Exception as e: await text_channel.send(f"An error occured: ```{e}```")

    # Close the client
    update_should_stop[0] = True
    await update_task
    await client.close()

async def create_song_embed(song: str, data: dict, color: Color = Color.blue()) -> Embed:
    return (
        Embed(title=data["title"], color=color, url=f"https://youtube.com/watch?v={song}")
        .set_image(url=data["thumbnail_url"])
        .add_field(name="Artist", value=data["artist"])
        .add_field(name="Duration", value=f"{data['duration'] // 60:02d}:{data['duration'] % 60:02d}")
    )

async def play_next_song(status_message: Message, voice_channel: VoiceChannel):
    # Get the members of the voice channel
    members = {str(member.id) for member in voice_channel.members if not member.bot}
    if not members:
        await status_message.edit(embed=Embed(title="No songs to play"))
        if client.voice_clients: await client.voice_clients[0].disconnect(force=False)
        return await sleep(10)
    
    # Find the next song
    if playlist:
        message, song = playlist.pop(0)
        await message.delete()
    else:
        song = await next_song(members)
        if song is None:
            await status_message.edit(embed=Embed(title="No songs to play"))
            if client.voice_clients: await client.voice_clients[0].disconnect(force=False)
            return await sleep(10)

    # Update the status message
    song_data = await load_song_data(song)
    await status_message.edit(embed=await create_song_embed(song, song_data))

    # Play the song
    source = await load_song(song)
    voice: VoiceClient = client.voice_clients[0] if client.voice_clients else await voice_channel.connect() # type: ignore
    voice.play(source)

    # Wait a bit
    await sleep(5)

    # Wait for the song to finish
    global skip_count
    while voice.is_playing() and skip_count == 0:
        song_data["duration"] -= 5
        await status_message.edit(embed=await create_song_embed(song, song_data, Color.green()))
        await sleep(5)
    if skip_count > 0:
        if voice.is_playing(): voice.stop()
        skip_count -= 1

async def download_songs(channel: TextChannel, songs: set[str], silent = False):
    songs = {song for song in songs if not await is_downloaded(song)}
    if len(songs) == 0:
        if not silent:
            response = await channel.send(embed=Embed(title=f"Nothing to download", color=Color.red()))
            await response.delete(delay=10)
    else:
        response = await channel.send(embed=Embed(title=f"Will download {len(songs)} song{'s' if len(songs) > 1 else ''}", color=Color.gold()))
        for i, song in enumerate(songs):
            await response.edit(embed=Embed(title=f"Downloading {song} ({i + 1}/{len(songs)})", color=Color.gold(), url=f"https://youtube.com/watch?v={song}"))
            try: await download(song)
            except Exception as e: await channel.send(f"An error occured: ```{e}```")
        await response.edit(embed=Embed(title=f"Downloaded {len(songs)} song{'s' if len(songs) > 1 else ''}", color=Color.green()))
        await response.delete(delay=10)

async def add_to_playlist(text_channel: TextChannel, song: str):
    message = await text_channel.send(embed=await create_song_embed(song, await load_song_data(song)))
    playlist.append((message, song))
    await message.add_reaction("❌")

@client.event
async def on_message(message: Message):
    if message.author.bot: return
    if message.channel.id != 1210446807046430770:
        if randint(0, 20) == 0:
            await send_generated_message(message.channel)
        return
    command = message.content.split(" ")[0]
    args = " ".join(message.content.split(" ")[1:])
    channel: TextChannel = message.channel # type: ignore
    member = str(message.author.id)
    await message.delete()

    if command in ("skip", "s"):
        global skip_count
        skip_count += 1
    
    elif command in ("remove", "delete", "rm", "r", "d"):
        songs = await resolve_query(args)
        removed_count = 0
        for song in songs:
            if await remove_from_member(member, song): removed_count += 1
        response = await channel.send(embed=Embed(
            title=f"Removed {removed_count} song{'s' if removed_count > 1 else ''}",
            color=Color.red()
        ))
        await response.delete(delay=10)

    elif command in ("download", "down", "load", "dl", "d", "add", "a"):
        songs = await resolve_query(args)
        for song in songs:
            await add_to_member(member, song)
        await download_songs(channel, set(songs))
    
    else:
        songs = await resolve_query(command)
        for song in songs:
            await add_to_member(member, song)
        await download_songs(channel, set(songs), silent=True)
        if not songs:
            response = await channel.send(embed=Embed(title="No songs found", color=Color.red()))
            await response.delete(delay=10)
        for song in songs:
            await add_to_playlist(channel, song)

@client.event
async def on_reaction_add(reaction: Reaction, member: Member):
    if member.bot: return
    for i, (message, _) in enumerate(playlist):
        if message.id == reaction.message.id:
            playlist.pop(i)
            await message.delete()
            break

client.run(token=environ["DISCORD_TOKEN"], reconnect=False, log_handler=None)