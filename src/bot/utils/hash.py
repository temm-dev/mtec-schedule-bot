import hashlib

from config.other import trash_simbols


async def generate_hash(schedule: list[list[str]]) -> str:
    clean_text = "".join("".join(pair) for pair in schedule)

    for i in trash_simbols:
        clean_text = clean_text.replace(i, "")

    clean_text = clean_text.strip()
    clean_text = clean_text.lower()

    return hashlib.md5(clean_text.encode()).hexdigest()
