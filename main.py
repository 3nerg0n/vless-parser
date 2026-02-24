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

FILE_PATH_INT = "sub_vless_3nerg0n_92sh81"  # Основной файл
FILE_PATH_RU = "Sub_ru"                     # Файл для RU конфигов

REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Списки ключевых слов
KEYWORDS_INT = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇫🇷", "france", "🇰🇿", "kazakhstan", "🇱🇻", "latvia", "🇨🇭", "switzerland", "🇸🇪", "sweden", "🇫🇮", "finland"]
KEYWORDS_RU = ["🇷🇺", "russia", "ru"]

def parse_vless_links(raw_data):
    """Парсит ссылки и разделяет их на международные и российские"""
    try:
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data

    lines = decoded_data.splitlines()
    int_links = []
    ru_links = []

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            # Фильтр по TCP + Reality (как в исходном коде)
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            
            if not (is_tcp and is_reality):
                continue

            name = unquote(parsed.fragment).lower()
            
            # Проверка на RU
            if any(k in name for k in KEYWORDS_RU):
                ru_links.append(line)
            # Проверка на международные
            elif any(k in name for k in KEYWORDS_INT):
                int_links.append(line)
        except:
            continue
            
    return int_links, ru_links

def get_data_with_retry(url, retries=3):
    """Скачивает данные с одной ссылки"""
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка при скачивании {url} (попытка {i+1}): {e}")
            if i < retries - 1:
                time.sleep(5)
            else:
                return ""

def upload_to_github(repo, path, content, msg_tag):
    """Вспомогательная функция для обновления файла в репозитории"""
    try:
        try:
            contents = repo.get_contents(path)
            # Если контент не изменился, не тратим лимиты API
            if contents.decoded_content.decode('utf-8') == content:
                print(f"[{path}] Изменений нет. Пропускаем.")
                return

            repo.update_file(
                path=path,
                message=f"Auto-update {msg_tag}: {len(content.splitlines())} configs",
                content=content,
                sha=contents.sha
            )
            print(f"[{path}] Файл обновлен!")
        except Exception:
            # Если файл не существует, создаем его
            repo.create_file(
                path=path,
                message=f"Initial creation {msg_tag}",
                content=content
            )
            print(f"[{path}] Файл создан.")
    except Exception as e:
        print(f"Ошибка при работе с GitHub для {path}: {e}")

def update_github():
    all_int_links = []
    all_ru_links = []

    # 1. Собираем данные
    for url in SOURCE_URLS:
        print(f"Обработка источника: {url}")
        raw_data = get_data_with_retry(url)
        if raw_data:
            int_l, ru_l = parse_vless_links(raw_data)
            all_int_links.extend(int_l)
            all_ru_links.extend(ru_l)
            print(f"Найдено: INT={len(int_l)}, RU={len(ru_l)}")

    # 2. Удаляем дубликаты
    unique_int = list(dict.fromkeys(all_int_links))
    unique_ru = list(dict.fromkeys(all_ru_links))
    
    print(f"Итого уникальных: INT={len(unique_int)}, RU={len(unique_ru)}")

    # 3. Обновляем GitHub
    try:
        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Обновляем основной международный файл
        content_int = "\n".join(unique_int) if unique_int else ""
        upload_to_github(repo, FILE_PATH_INT, content_int, "INT")
        
        # Обновляем файл RU
        content_ru = "\n".join(unique_ru) if unique_ru else ""
        upload_to_github(repo, FILE_PATH_RU, content_ru, "RU")

    except Exception as e:
        print(f"Критическая ошибка GitHub API: {e}")

if __name__ == "__main__":
    update_github()
