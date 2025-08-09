<!-- # mtec-schedule-bot

_Unofficial volunteer project_ \
_Created on the initiative of a student for students_

This is a bot created to help students keep track of appearances and schedule changes.


## 💡 Idea

The user opens the bot in telegram, selects his study group, after which the current schedule and changes in pairs in the schedule (if any) will be automatically sent to him.

In addition, there are additional functions for the convenience of students.

## ⚙️ Technology stack:
- **Backend**  
  • Python 3.13  
  • ~~telebot (Telegram Bot API)~~  
  • aiogram3 (Telegram Bot API)  
  • asyncio, aiohttp, aiofiles  
  • beautifulsoup4  

- **Databases**  
  • SQLite3  
  • Redis  

- **Infrastructure**  
  • Docker   -->

<h1 align="center">📅 MTEC Schedule Bot</h1>

<p align="center">
  <img src="assets/mtec-black-back.png" alt="">
</p>


<p align="center">
  <a href="https://python.org/">
    <img src="https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white" alt="Python 3.13">
  </a>
  <a href="https://aiogram.dev/">
    <img src="https://img.shields.io/badge/Aiogram-3.0-green?logo=telegram&logoColor=white" alt="Aiogram 3">
  </a>
  <a href="https://www.docker.com/">
    <img src="https://img.shields.io/badge/Docker-✓-blue?logo=docker&logoColor=white" alt="Docker">
  </a>
</p>

<p align="center">
  <strong>Unofficial Telegram bot for college schedule tracking</strong><br>
  <i>Created by student for students</i>
</p>


## 💡 Project idea

A telegram bot for automatically tracking college class schedules. Main functions:

- **Automatic distribution** of the schedule when it appears
- **Notifications of changes** in the schedule (substitutions, cancellations of pairs)
- **Additional features** for students:
  - Call schedule
  - Electronic journal
  - A friend's schedule

## ⚙️ Technology stack

### **Backend**
- Python 3.13
- Aiogram 3 (asynchronous framework for Telegram bots)
- BeautifulSoup4 (HTML parsing)
- Asyncio/Aiohttp/Aiofiles (asynchronous operations)

### **Databases**
- SQLite3 (main data warehouse)

### **Infrastructure**
- Docker (application containerization)

## 🚀 Quick Start

### Preliminary requirements
- Python 3.13
- Docker (optional)
- Telegram-bot token ([@BotFather](https://t.me/BotFather))
- SECRET_KEY to encrypt the database
- ADMIN_ID for the admin panel

### Installation
```bash
# Clone the repository
git clone https://github.com/temm-dev/mtec-schedule-bot.git
cd mtec-schedule-bot

# Install dependencies
poetry install

# Launch
python src/bot/main.py
```

<br>

> **Have a nice day!** 🍀