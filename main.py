import os
import requests
import base64
import time
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- КОНФИГУРАЦИЯ ---
SOURCE_URL = "https://etoneya.a9fm.site/1"
# Меняем имя на config без расширения
FILE_PATH = "config" 
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

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
    target_keywords = ["germany", "netherlands"]

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
            if i < retries - 1:
                time.sleep(5)
            else:
                raise

def update_github():
    try:
        raw_data = get_data_with_retry(SOURCE_URL)
        links = parse_vless_links(raw_data)
        
        if not links:
            print("Конфиги не найдены.")
            return

        # Формируем текст и кодируем его в Base64 для лучшей совместимости
        content_raw = "\n".join(links)
        content_b64 = base64.b64encode(content_raw.encode('utf-8')).decode('utf-8')

        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            contents = repo.get_contents(FILE_PATH)
            # Обновляем
            repo.update_file(
                path=FILE_PATH,
                message="Update subscription (Base64)",
                content=content_b64,
                sha=contents.sha
            )
            print(f"Обновлено. Конфигов внутри: {len(links)}")
        except:
            # Создаем
            repo.create_file(
                path=FILE_PATH,
                message="Initial subscription",
                content=content_b64
            )
            print("Файл config создан.")
            
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    update_github()
