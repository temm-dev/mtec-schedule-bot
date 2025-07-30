from config.paths import WORKSPACE


async def print_sent(user_id: int):
    print(f"\t\t🟩 {user_id} | Отправлено")


async def log(data, type_data: str = "ms"):
    log_text = f"{data.from_user.id} - @{data.from_user.username} - {data.from_user.first_name} - {data.from_user.last_name}"

    if type_data == "ms":
        log_text += f"\n{data.text}\n\n"
    else:
        log_text += f"\n{data.data}\n\n"

    with open(f"{WORKSPACE}logs.txt", "a") as logs:
        logs.write(log_text)
