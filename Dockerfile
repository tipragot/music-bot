FROM python:3.12-slim

RUN apt-get update && apt-get install ffmpeg -y
RUN pip install discord PyNaCl aiofiles mutagen yt-dlp pytube pydub

WORKDIR /app
COPY *.py ./

WORKDIR /data
VOLUME [ "/data" ]

CMD [ "python3", "/app/main.py" ]
