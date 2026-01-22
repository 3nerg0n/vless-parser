import os
import requests
import base64
import time
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- НАСТРОЙКИ ---
SOURCE_URLS = [
    "https://etoneya.a9fm.site/1",
    "https://etoneya.a9fm.site/2"
]
FILE_PATH = "sub_vless_3nerg0n_92sh81"  # Файл без расширения 
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
    target_keywords = ["germany", "netherlands", "nederland", "🇩🇪", "🇳🇱"]

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            # Фильтр: только TCP и REALITY
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            
            if not (is_tcp and is_reality):
                continue

            # Фильтр по названию
            name = unquote(parsed.fragment).lower()
            if any(k in name for k in target_keywords):
                filtered_links.append(line)
        except:
            continue
    return filtered_links

def update_github():
    all_links = []
    for url in SOURCE_URLS:
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code == 200:
                links = parse_vless_links(response.text)
                all_links.extend(links)
        except:
            continue

    # Удаляем дубликаты
    unique_links = list(dict.fromkeys(all_links))
    content = "\n".join(unique_links)

    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    try:
        contents = repo.get_contents(FILE_PATH)
        if contents.decoded_content.decode('utf-8') == content:
            print("Изменений нет.")
            return
        repo.update_file(path=FILE_PATH, message="Fast update", content=content, sha=contents.sha)
    except:
        repo.create_file(path=FILE_PATH, message="Initial config", content=content)
    
    print(f"Готово! Собрано ссылок: {len(unique_links)}")

if __name__ == "__main__":
    update_github()
