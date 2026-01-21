import os
import requests
import base64
import time
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- КОНФИГУРАЦИЯ ---
SOURCE_URL = "https://etoneya.a9fm.site/1"
FILE_PATH = "configs.txt" 
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

# Заголовки, чтобы сайт думал, что мы — браузер
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def parse_vless_links(raw_data):
    try:
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data

    lines = decoded_data.splitlines()
    filtered_links = []
    target_keywords = ["germany", "netherlands", "nederland"]
    strict_iso = ["de", "nl"]

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            
            if not (is_tcp and is_reality):
                continue

            name = unquote(parsed.fragment).lower()
            has_location = any(k in name for k in target_keywords)
            
            if not has_location:
                name_words = name.replace('-', ' ').replace('[', ' ').replace(']', ' ').replace('_', ' ').split()
                if any(iso in name_words for iso in strict_iso):
                    has_location = True

            if has_location:
                filtered_links.append(line)
        except:
            continue
    return filtered_links

def get_data_with_retry(url, retries=3):
    """Скачивает данные с повторными попытками при ошибках сети"""
    for i in range(retries):
        try:
            # Увеличили таймаут до 30 секунд и добавили Headers
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Попытка {i+1} не удалась: {e}")
            if i < retries - 1:
                time.sleep(5) # Ждем 5 секунд перед следующей попыткой
            else:
                raise

def update_github():
    try:
        raw_data = get_data_with_retry(SOURCE_URL)
        links = parse_vless_links(raw_data)
        
        content = "\n".join(links) if links else ""

        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            contents = repo.get_contents(FILE_PATH)
            current_content = contents.decoded_content.decode('utf-8')
            if current_content == content:
                print("Изменений нет. Пропускаем.")
                return

            repo.update_file(
                path=FILE_PATH,
                message="Auto-update: refined filtering",
                content=content,
                sha=contents.sha
            )
            print(f"Успех! Найдено конфигов: {len(links)}")
        except:
            repo.create_file(
                path=FILE_PATH,
                message="Initial VLESS configs",
                content=content
            )
            print("Файл создан.")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        # Не вызываем sys.exit(1), чтобы Actions не помечался как упавший, 
        # если сайт просто временно лежит.
        
if __name__ == "__main__":
    update_github()
