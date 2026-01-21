import os
import requests
import base64
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- КОНФИГУРАЦИЯ ---
SOURCE_URL = "https://etoneya.a9fm.site/1"
FILE_PATH = "configs.txt"  # Имя файла в репозитории
REPO_NAME = os.getenv("GITHUB_REPOSITORY")  # Автоматически подхватит имя вашего репо
TOKEN = os.getenv("MY_GITHUB_TOKEN")

def parse_vless_links(raw_data):
    try:
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data

    lines = decoded_data.splitlines()
    filtered_links = []

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            name = unquote(parsed.fragment).lower()
            has_location = any(x in name for x in ["germany", "netherlands", "de", "nl", "🇩🇪", "🇳🇱"])

            if is_tcp and is_reality and has_location:
                filtered_links.append(line)
        except:
            continue
    return filtered_links

def update_github():
    # 1. Получаем отфильтрованные данные
    response = requests.get(SOURCE_URL, timeout=10)
    response.raise_for_status()
    links = parse_vless_links(response.text)
    
    if not links:
        print("Подходящих конфигов не найдено. Файл не будет обновлен.")
        return

    content = "\n".join(links)

    # 2. Работа с GitHub API
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    try:
        # Проверяем, существует ли файл, чтобы получить его SHA (нужен для обновления)
        contents = repo.get_contents(FILE_PATH)
        repo.update_file(
            path=FILE_PATH,
            message="Auto-update VLESS configs",
            content=content,
            sha=contents.sha
        )
        print("Файл успешно обновлен на GitHub!")
    except Exception as e:
        # Если файла нет, создаем его
        repo.create_file(
            path=FILE_PATH,
            message="Initial VLESS configs",
            content=content
        )
        print("Файл был создан и заполнен.")

if __name__ == "__main__":
    update_github()
