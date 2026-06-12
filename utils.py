def clean_username(raw: str) -> str:
    return raw.strip().lstrip('@').lower()

def user_label(user) -> str:
    return f"@{user.username}" if user.username else f"ID{user.id}"
