import os
import requests
import base64
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- КОНФИГУРАЦИЯ ---
SOURCE_URL = "https://etoneya.a9fm.site/1"
FILE_PATH = "configs.txt" 
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

def parse_vless_links(raw_data):
    try:
        # Пытаемся декодировать base64, если это подписка
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data

    lines = decoded_data.splitlines()
    filtered_links = []

    # Список ключевых слов (более строгий)
    target_keywords = ["germany", "netherlands"]
    # Список сокращений, которые ищем только как отдельные слова или в скобках
    strict_iso = ["de", "nl"]

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            # 1. Проверка протоколов
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            
            if not (is_tcp and is_reality):
                continue

            # 2. Проверка названия (локации) в фрагменте (#...)
            name = unquote(parsed.fragment).lower()
            
            # Проверяем наличие флагов или полных названий
            has_location = any(k in name for k in target_keywords)
            
            # Если не нашли, проверяем ISO-коды (чтобы de не нашлось в слове index)
            if not has_location:
                # Ищем " de " или "[de]" или "de-" и т.д.
                name_words = name.replace('-', ' ').replace('[', ' ').replace(']', ' ').replace('_', ' ').split()
                if any(iso in name_words for iso in strict_iso):
                    has_location = True

            if has_location:
                filtered_links.append(line)
        except:
            continue
            
    return filtered_links

def update_github():
    response = requests.get(SOURCE_URL, timeout=10)
    response.raise_for_status()
    links = parse_vless_links(response.text)
    
    # Если ничего не нашли, запишем пустую строку или оповещение (чтобы файл не был старым)
    content = "\n".join(links) if links else ""

    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    try:
        contents = repo.get_contents(FILE_PATH)
        # Если содержимое не изменилось, не создаем лишних коммитов
        current_content = contents.decoded_content.decode('utf-8')
        if current_content == content:
            print("Изменений нет. Пропускаем обновление.")
            return

        repo.update_file(
            path=FILE_PATH,
            message="Auto-update: refined filtering",
            content=content,
            sha=contents.sha
        )
        print(f"Файл обновлен! Найдено конфигов: {len(links)}")
    except Exception as e:
        repo.create_file(
            path=FILE_PATH,
            message="Initial VLESS configs",
            content=content
        )
        print("Файл создан.")

if __name__ == "__main__":
    update_github()
