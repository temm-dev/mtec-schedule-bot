import os
from datetime import datetime

import psutil
from config.other import days_of_week


def day_week_by_date(date: str):
    date_object = datetime.strptime(date, "%d.%m.%Y")
    day_of_week_number = date_object.weekday()
    day_of_week_name = days_of_week[day_of_week_number]
    return day_of_week_name


def get_memory_info():
    server_mem = psutil.virtual_memory()
    process = psutil.Process(os.getpid())
    process_mem = process.memory_info()

    info = f"""
[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]
ОБЩАЯ ПАМЯТЬ СЕРВЕРА:
    Всего: {server_mem.total / (1024**3):.2f} GB
    Используется: {server_mem.used / (1024**3):.2f} GB
    Свободно: {server_mem.available / (1024**3):.2f} GB
    Использовано (%): {server_mem.percent}%

ПАМЯТЬ ВАШЕГО БОТА (PID: {process.pid}):
    RSS (физическая): {process_mem.rss / (1024**2):.2f} MB
    VMS (виртуальная): {process_mem.vms / (1024**2):.2f} MB
    Доля от общей (%): {(process_mem.rss / server_mem.total) * 100:.2f}%
    """
    return info


def format_names(names: list[str]):
    result = []
    for name in names:
        parts = name.split()
        if len(parts) >= 3:
            surname, first_name, patronymic = parts[0], parts[1], parts[2]
            formatted_name = f"{surname} {first_name[0]}. {patronymic[0]}."
            result.append(formatted_name)
        else:
            result.append(name)

    return result
