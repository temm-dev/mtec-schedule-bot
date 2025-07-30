FROM python:3.13-slim

RUN mkdir -p /usr/src/mtecbot
WORKDIR /usr/src/mtecbot

COPY . /usr/src/mtecbot

RUN pip3 install poetry

RUN poetry --no-root install

CMD [ "poetry", "run", "python3", "src/bot/main.py" ]