import os
import requests
import base64
import time
import socket
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- КОНФИГУРАЦИЯ ---
# Теперь здесь список ссылок
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
FILE_PATH = "sub_vless_3nerg0n_92sh82"  # Файл без расширения
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def check_tcp_connectivity(link, timeout=3):
    """Проверяет доступность TCP порта сервера"""
    try:
        parsed = urlparse(link)
        # В vless://uuid@host:port host и port находятся в netloc
        netloc = parsed.netloc
        if '@' in netloc:
            host_port = netloc.split('@')[1]
        else:
            host_port = netloc
        
        if ':' in host_port:
            host, port = host_port.split(':')
            port = int(port)
        else:
            host = host_port
            port = 443 # по умолчанию для reality

        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def parse_vless_links(raw_data):
    """Парсит и фильтрует ссылки из сырых данных"""
    try:
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data

    lines = decoded_data.splitlines()
    filtered_links = []
    target_keywords = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇱🇻", "latvia", "🇫🇮", "finland", "RU", "russia"]

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
                return "" # Если все попытки провалены, возвращаем пустую строку

def update_github():
    all_filtered_links = []

    # 1. Собираем данные со всех источников
    for url in SOURCE_URLS:
        print(f"Обработка источника: {url}")
        raw_data = get_data_with_retry(url)
        if raw_data:
            links = parse_vless_links(raw_data)
            all_filtered_links.extend(links)
            print(f"Найдено подходящих конфигов: {len(links)}")

    # 2. Удаляем дубликаты (если один и тот же сервер есть в разных подписках)
    unique_links = list(dict.fromkeys(all_filtered_links))
    print(f"Всего уникальных конфигов после фильтрации: {len(unique_links)}")

    content = "\n".join(unique_links) if unique_links else ""

	  # 3. ПРОВЕРКА НА ДОСТУПНОСТЬ (Check connectivity)
    print("Начинаю проверку доступности серверов (TCP Check)...")
    working_links = []
    for link in unique_links:
        if check_tcp_connectivity(link):
            working_links.append(link)
    
    print(f"Итого рабочих конфигов: {len(working_links)}")
    content = "\n".join(working_links) if working_links else ""

    # 4. Обновляем GitHub
    try:
        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            contents = repo.get_contents(FILE_PATH)
            if contents.decoded_content.decode('utf-8') == content:
                print("Изменений нет. Пропускаем обновление.")
                return

            repo.update_file(
                path=FILE_PATH,
                message=f"Auto-update: {len(unique_links)} configs from multiple sources",
                content=content,
                sha=contents.sha
            )
            print("Файл успешно обновлен на GitHub!")
        except:
            repo.create_file(
                path=FILE_PATH,
                message="Initial config creation",
                content=content
            )
            print("Файл создан.")
    except Exception as e:
        print(f"Ошибка GitHub API: {e}")

if __name__ == "__main__":
    update_github()
