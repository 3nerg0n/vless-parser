import os
import requests
import base64
import time
from urllib.parse import urlparse, parse_qs, unquote
from github import Github, GithubException

# --- КОНФИГУРАЦИЯ ---
SOURCE_URLS = [
    "https://etoneya.a9fm.site/1",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/wl.txt",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/selected.txt",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/merged.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://nowmeow.pw/8ybBd3fdCAQ6Ew5H0d66Y1hMbh63GpKUtEXQClIu/whitelist",
    "https://raw.githubusercontent.com/gbwltg/gbwl/refs/heads/main/m2EsPqwmlc"
]
FILE_PATH = "sub_vless_3nerg0n_92sh81" 
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def decode_base64(data):
    """Декодирует base64 с исправлением паддинга"""
    data = data.strip()
    try:
        # Добавляем недостающие '=' для корректного base64
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except Exception:
        return data

def parse_vless_links(raw_data):
    """Парсит и фильтрует ссылки"""
    decoded_data = decode_base64(raw_data)
    lines = decoded_data.splitlines()
    filtered_links = []
    # Ключевые слова в нижнем регистре для удобства поиска
    target_keywords = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇱🇻", "latvia", "🇫🇮", "finland", "ru", "russia"]

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            # Проверка на Reality + TCP
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            
            if not (is_tcp and is_reality):
                continue

            # Проверка страны в названии (фрагменте ссылки)
            name = unquote(parsed.fragment).lower()
            if any(k in name for k in target_keywords):
                filtered_links.append(line)
        except:
            continue
    return filtered_links

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка при скачивании {url} (попытка {i+1}): {e}")
            if i < retries - 1:
                time.sleep(5)
    return ""

def update_github():
    all_filtered_links = []

    for url in SOURCE_URLS:
        print(f"Обработка источника: {url}")
        raw_data = get_data_with_retry(url)
        if raw_data:
            links = parse_vless_links(raw_data)
            all_filtered_links.extend(links)
            print(f"Найдено подходящих конфигов: {len(links)}")

    unique_links = list(dict.fromkeys(all_filtered_links))
    print(f"Всего уникальных конфигов после фильтрации: {len(unique_links)}")

    if not unique_links:
        print("Новых конфигов не найдено. Обновление отменено, чтобы не затереть старые данные.")
        return

    content = "\n".join(unique_links)

    try:
        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            # Пытаемся получить существующий файл
            contents = repo.get_contents(FILE_PATH)
            old_content = contents.decoded_content.decode('utf-8')
            
            if old_content.strip() == content.strip():
                print("Изменений нет. Пропускаем обновление.")
                return

            # Если файл есть, обновляем его, обязательно передавая sha
            repo.update_file(
                path=FILE_PATH,
                message=f"Auto-update: {len(unique_links)} configs",
                content=content,
                sha=contents.sha
            )
            print("Файл успешно обновлен!")
            
        except GithubException as e:
            if e.status == 404:
                # Если файла нет, создаем его
                repo.create_file(
                    path=FILE_PATH,
                    message="Initial config creation",
                    content=content
                )
                print("Файл создан.")
            else:
                print(f"Ошибка GitHub API при получении файла: {e}")
                
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    update_github()
