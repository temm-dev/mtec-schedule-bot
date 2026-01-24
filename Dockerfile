FROM python:3.13-slim

RUN mkdir -p /mtec-schedule-bot
WORKDIR /mtec-schedule-bot

COPY . /mtec-schedule-bot

RUN pip install poetry
RUN poetry --no-root install

CMD [ "poetry", "run", "python3", "src/bot/main.py" ]
