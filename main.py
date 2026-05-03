import os
import requests
import base64
import time
import subprocess
import socket
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- КОНФИГУРАЦИЯ ---
SOURCE_URLS = [
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/merged.txt",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/selected.txt",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/wl.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/EtoNeYaProject/etoneyaproject.github.io/refs/heads/main/1",
    "https://raw.githubusercontent.com/EtoNeYaProject/etoneyaproject.github.io/refs/heads/main/whitelist",
    "https://nowmeow.pw/8ybBd3fdCAQ6Ew5H0d66Y1hMbh63GpKUtEXQClIu/whitelist"
]
FILE_PATH = "sub_vless_3nerg0n_92sh81" 
MAX_WORKERS = 40 

# Список разрешенных префиксов IP
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
            
        # Фильтрация только по списку префиксов IP
        if not any(host.startswith(prefix) for prefix in ALLOWED_IP_PREFIXES):
            return None

        port = 443
        if parsed.port:
            port = int(parsed.port)
            
        if is_tcp_reachable(host, port):
            return line
            
    except:
        pass
    return None

# ... (Остальные функции get_data_with_retry, run_git_command, update_repository остаются без изменений) ...

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
    print(f"Найдено {len(unique_raw)} ссылок. Начинаю проверку IP и TCP...")

    verified_links = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_link = {executor.submit(check_single_link, link): link for link in unique_raw}
        for future in as_completed(future_to_link):
            result = future.result()
            if result:
                verified_links.append(result)

    print(f"Готово. Найдено подходящих: {len(verified_links)}")
    if verified_links:
        update_repository("\n".join(verified_links), len(verified_links))

if __name__ == "__main__":
    main()
