from datetime import datetime

from config.other import days_of_week


def day_week_by_date(date: str):
    date_object = datetime.strptime(date, "%d.%m.%Y")
    day_of_week_number = date_object.weekday()
    day_of_week_name = days_of_week[day_of_week_number]
    return day_of_week_name


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
