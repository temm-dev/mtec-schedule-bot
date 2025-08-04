FROM python:3.13-slim

RUN mkdir -p /usr/src/mtec-schedule-bot
WORKDIR /usr/src/mtec-schedule-bot

COPY . /usr/src/mtec-schedule-bot

RUN pip3 install poetry

RUN poetry --no-root install

CMD [ "poetry", "run", "python3", "src/bot/main.py" ]