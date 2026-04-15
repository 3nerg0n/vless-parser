import os
import requests
import base64
import time
import subprocess
import socket
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- КОНФИГУРАЦИЯ ---
SOURCE_URLS = [
    "https://gitverse.ru/api/repos/nloverx/EtoNeYa_Subs/raw/branch/master/1",
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
MAX_WORKERS = 30 

# 1. Список разрешенных стран (ключевые слова в названии)
TARGET_KEYWORDS = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇫🇮", "finland"]

# 2. Список разрешенных префиксов IP (только для тех, кто прошел фильтр по стране)
ALLOWED_IP_PREFIXES = [
    "217.16", "84.201", "51.250", "78.159", "81.200",
    "158.160", "5.188", "62.152", "109.120", "212.233", "87.239"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def is_tcp_reachable(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def decode_base64(data):
    data = data.strip()
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except:
        return data

def check_single_link(line):
    """Последовательная фильтрация: Протокол -> Страна -> IP -> Доступность"""
    try:
        parsed = urlparse(line)
        params = parse_qs(parsed.query)
        
        # Шаг 1: Проверка протокола
        is_tcp = params.get('type', [''])[0].lower() == 'tcp'
        is_reality = params.get('security', [''])[0].lower() == 'reality'
        if not (is_tcp and is_reality):
            return None

        # Шаг 2: Фильтрация по стране (название в фрагменте #)
        name = unquote(parsed.fragment).lower()
        if not any(k in name for k in TARGET_KEYWORDS):
            return None # Если страны нет в названии, отбрасываем сразу

        # Шаг 3: Фильтрация по IP (среди тех, кто прошел проверку страны)
        host = parsed.hostname
        if not host:
            return None
            
        # Проверяем, начинается ли хост на один из разрешенных префиксов
        if not any(host.startswith(prefix) for prefix in ALLOWED_IP_PREFIXES):
            return None # Если IP не подходит, отбрасываем

        # Шаг 4: Проверка порта (финальная проверка живой/мертвый)
        port = int(parsed.port) if parsed.port else 443
        if is_tcp_reachable(host, port):
            return line
            
    except:
        pass
    return None

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.text
        except:
            if i < retries - 1:
                time.sleep(2)
    return ""

def run_git_command(command):
    try:
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка Git: {e.stderr}")

def update_repository(content, count):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    try:
        run_git_command('git config --global user.name "github-actions[bot]"')
        run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        run_git_command(f'git add {FILE_PATH}')
        
        status = subprocess.run(f'git status --porcelain {FILE_PATH}', shell=True, capture_output=True, text=True).stdout.strip()
        if not status:
            print("Изменений нет.")
            return

        run_git_command(f'git commit -m "Auto-update: {count} verified links (Country + IP filter)"')
        run_git_command('git push')
        print(f"✅ Успешно обновлено: {count} конфигов")
    except Exception as e:
        print(f"❌ Ошибка Git: {e}")

def main():
    raw_links = []

    for url in SOURCE_URLS:
        print(f"Скачивание: {url}")
        data = get_data_with_retry(url)
        if data:
            decoded = decode_base64(data)
            for line in decoded.splitlines():
                line = line.strip()
                if line.startswith("vless://"):
                    raw_links.append(line)

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} уникальных ссылок. Начинаю строгую фильтрацию...")

    verified_links = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_link = {executor.submit(check_single_link, link): link for link in unique_raw}
        
        completed = 0
        for future in as_completed(future_to_link):
            result = future.result()
            if result:
                verified_links.append(result)
            
            completed += 1
            if completed % 100 == 0:
                print(f"Проверено: {completed}/{len(unique_raw)}...")

    print(f"Фильтрация завершена. Найдено подходящих и живых: {len(verified_links)}")

    if not verified_links:
        print("Нет конфигов, соответствующих обоим условиям (Страна + IP).")
        return

    content = "\n".join(verified_links)
    update_repository(content, len(verified_links))

if __name__ == "__main__":
    main()
