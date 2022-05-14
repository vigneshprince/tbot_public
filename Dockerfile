FROM python:3.9-alpine as base
WORKDIR /app
COPY . .
RUN apk update && apk add git postgresql-dev gcc musl-dev ffmpeg libc-dev zlib zlib-dev jpeg-dev && pip install -r requirements.txt
ENV SPOTIPY_CLIENT_ID=' '
ENV SPOTIPY_CLIENT_SECRET=' '
ENTRYPOINT ["python","run_all.py"]