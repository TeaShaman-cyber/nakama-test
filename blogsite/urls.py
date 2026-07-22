from urllib.parse import quote

_REPO = "https://github.com/TeaShaman-cyber/nakama-test"
_TRANSLIT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


def normalize_base_path(base_path: str) -> str:
    core = base_path.strip("/")
    return "/" if not core else f"/{core}/"


def site_url(relative: str, base_path: str) -> str:
    return normalize_base_path(base_path) + relative.lstrip("/")


def article_url(slug: str, base_path: str) -> str:
    return site_url(f"journal/{slug}/", base_path)


def slugify_series(name: str) -> str:
    lowered = name.lower().translate(_TRANSLIT)
    out: list[str] = []
    dash = False
    for char in lowered:
        if char.isalnum():
            out.append(char)
            dash = False
        elif not dash:
            out.append("-")
            dash = True
    return "".join(out).strip("-")


def series_url(name: str, base_path: str) -> str:
    return site_url(f"series/{slugify_series(name)}/", base_path)


def source_url(source_name: str) -> str:
    return f"{_REPO}/blob/main/journal/{quote(source_name)}"


def history_url(source_name: str) -> str:
    return f"{_REPO}/commits/main/journal/{quote(source_name)}"
