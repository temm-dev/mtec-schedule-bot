from datetime import datetime

from config.other import days_of_week


def day_week_by_date(date: str):
    date_object = datetime.strptime(date, "%d.%m.%Y")
    day_of_week_number = date_object.weekday()
    day_of_week_name = days_of_week[day_of_week_number]
    return day_of_week_name
