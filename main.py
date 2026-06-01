import os
import requests
import base64
import time
import subprocess
import socket
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- КОНФИГУРАЦИЯ ---
SOURCE_URLS = [
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/merged.txt"
    
]
FILE_PATH = "sub_vless_3nerg0n_92sh81" 
MAX_WORKERS = 40 

ALLOWED_IP_PREFIXES = []

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
        if any(data.startswith(p) for p in ["vless://", "vmess://", "ss://", "trojan://"]):
            return data
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except:
        return data

def check_single_link(line):
    try:
        line = line.strip()
        if not line or "://" not in line:
            return None
        parsed = urlparse(line)
        host = parsed.hostname
        if not host:
            return None
        if not any(host.startswith(prefix) for prefix in ALLOWED_IP_PREFIXES):
            return None
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
    except:
        pass

def update_repository(content, count):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        run_git_command('git config --global user.name "github-actions[bot]"')
        run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        run_git_command(f'git add {FILE_PATH}')
        status = subprocess.run(f'git status --porcelain {FILE_PATH}', shell=True, capture_output=True, text=True).stdout.strip()
        if not status:
            return
        run_git_command(f'git commit -m "Auto-update: {count} valid configs"')
        run_git_command('git push')
    except Exception as e:
        print(f"Ошибка Git: {e}")

def main():
    raw_links = []
    for url in SOURCE_URLS:
        print(f"Скачивание: {url}")
        data = get_data_with_retry(url)
        if data:
            decoded = decode_base64(data)
            for line in decoded.splitlines():
                line = line.strip()
                if "://" in line:
                    raw_links.append(line)

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} ссылок. Фильтрация IP и TCP...")

    verified_links = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_link = {executor.submit(check_single_link, link): link for link in unique_raw}
        for future in as_completed(future_to_link):
            result = future.result()
            if result:
                verified_links.append(result)

    print(f"Готово. Доступно: {len(verified_links)}")
    if verified_links:
        update_repository("\n".join(verified_links), len(verified_links))

if __name__ == "__main__":
    main()
