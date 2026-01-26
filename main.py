import os
import requests
import time
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- КОНФИГУРАЦИЯ ---
SOURCE_URL = "https://etoneya.a9fm.site/1"
FILE_PATH = "sub_vless_3nerg0n_92sh81"  # Файл без расширения
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

# Заголовки для имитации браузера
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def parse_vless_links(raw_data):
    # Работаем напрямую с текстом без base64
    lines = raw_data.splitlines()
    filtered_links = []
    target_keywords = ["germany", "netherlands", "russia"]

    for line in lines:
        line = line.strip()
        # Если строка — это base64 (иногда весь файл зашифрован), попробуем декодировать
        if not line.startswith("vless://") and len(line) > 50:
            try:
                import base64
                decoded = base64.b64decode(line).decode('utf-8')
                return parse_vless_links(decoded) # Рекурсивно обрабатываем декодированный текст
            except:
                continue

        if not line.startswith("vless://"):
            continue

        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            # Проверка параметров
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            
            if not (is_tcp and is_reality):
                continue

            # Проверка названия
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
            print(f"Попытка {i+1} не удалась: {e}")
            if i < retries - 1:
                time.sleep(5)
            else:
                raise

def update_github():
    try:
        raw_data = get_data_with_retry(SOURCE_URL)
        links = parse_vless_links(raw_data)
        
        if not links:
            print("Подходящих конфигов не найдено.")
            # Чтобы очистить файл, если конфиги пропали:
            content = "" 
        else:
            content = "\n".join(links)

        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            # Обновление существующего файла
            contents = repo.get_contents(FILE_PATH)
            # Проверяем, изменилось ли что-то, чтобы не плодить коммиты
            if contents.decoded_content.decode('utf-8') == content:
                print("Контент не изменился. Пропускаем.")
                return

            repo.update_file(
                path=FILE_PATH,
                message="Update config (Plain Text)",
                content=content,
                sha=contents.sha
            )
            print(f"Файл обновлен. Найдено ссылок: {len(links)}")
        except:
            # Создание файла, если его нет
            repo.create_file(
                path=FILE_PATH,
                message="Initial config creation",
                content=content
            )
            print("Файл config создан.")
            
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    update_github()
