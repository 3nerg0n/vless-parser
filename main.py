import os
import requests
import base64
import time
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- КОНФИГУРАЦИЯ ---
SOURCE_URLS = [
    "https://etoneya.a9fm.site/1",
    "https://bp.wl.free.nf/confs/selected.txt",
    "https://bp.wl.free.nf/confs/wl.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt"
]

FILE_PATH_ALL = "sub_vless_3nerg0n_92sh81"  # Все конфиги
FILE_PATH_RU = "Sub_ru"                     # Только Россия

REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Ключевые слова для фильтрации (все страны)
KEYWORDS_ALL = [
    "🇩🇪", "germany", "🇳🇱", "netherlands", "🇫🇷", "france", 
    "🇰🇿", "kazakhstan", "🇱🇻", "latvia", "🇨🇭", "switzerland", 
    "🇸🇪", "sweden", "🇫🇮", "finland", "🇺🇸", "usa", "united states",
    "🇷🇺", "russia", "ru" # Россия тоже входит в общий список
]

# Ключевые слова только для России
KEYWORDS_RU_ONLY = ["🇷🇺", "russia", "ru"]

def parse_vless_links(raw_data):
    """Парсит ссылки и распределяет их: во все и отдельно в RU"""
    try:
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data

    lines = decoded_data.splitlines()
    all_found = []
    ru_found = []

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            # Фильтр: только TCP + Reality
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            if not (is_tcp and is_reality):
                continue

            name = unquote(parsed.fragment).lower()
            
            # 1. Проверяем для общего файла (все страны)
            if any(k in name for k in KEYWORDS_ALL):
                all_found.append(line)
            
            # 2. Проверяем отдельно для RU файла
            if any(k in name for k in KEYWORDS_RU_ONLY):
                ru_found.append(line)
        except:
            continue
            
    return all_found, ru_found

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка при скачивании {url} (попытка {i+1}): {e}")
            if i < retries - 1: time.sleep(5)
            else: return ""

def upload_to_github(repo, path, links, description):
    """Обновляет файл в GitHub, если есть изменения"""
    content = "\n".join(list(dict.fromkeys(links))) if links else ""
    
    try:
        try:
            contents = repo.get_contents(path)
            if contents.decoded_content.decode('utf-8') == content:
                print(f"[{path}] Изменений нет. Пропуск.")
                return

            repo.update_file(
                path=path,
                message=f"Auto-update {description}: {len(links)} configs",
                content=content,
                sha=contents.sha
            )
            print(f"[{path}] Успешно обновлен.")
        except:
            repo.create_file(
                path=path,
                message=f"Initial create {description}",
                content=content
            )
            print(f"[{path}] Файл создан.")
    except Exception as e:
        print(f"Ошибка GitHub API для {path}: {e}")

def update_github():
    final_all = []
    final_ru = []

    # 1. Собираем данные со всех источников
    for url in SOURCE_URLS:
        print(f"Обработка: {url}")
        raw_data = get_data_with_retry(url)
        if raw_data:
            all_l, ru_l = parse_vless_links(raw_data)
            final_all.extend(all_l)
            final_ru.extend(ru_l)
            print(f"Найдено: Всего={len(all_l)}, RU={len(ru_l)}")

    # 2. Инициализируем GitHub
    try:
        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Загружаем общий файл
        upload_to_github(repo, FILE_PATH_ALL, final_all, "All Countries")
        
        # Загружаем файл только с RU
        upload_to_github(repo, FILE_PATH_RU, final_ru, "Russia Only")

    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    update_github()
