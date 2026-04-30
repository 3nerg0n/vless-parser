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
MAX_WORKERS = 50 

# Префиксы IP для фильтрации
ALLOWED_IP_PREFIXES = [
    "217.16", "84.201", "51.250", "78.159", "81.200",
    "158.160", "5.188", "62.152", "109.120", "212.233", "87.239"
]

# Ключевые слова стран
TARGET_KEYWORDS = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇫🇮", "finland", "ru", "russia"]

def is_tcp_reachable(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def decode_base64(data):
    data = data.strip()
    try:
        if "://" in data: return data
        missing_padding = len(data) % 4
        if missing_padding: data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except: return data

def parse_vless_to_dict(link):
    """Парсит vless и проверяет фильтры"""
    try:
        parsed = urlparse(link)
        if parsed.scheme != 'vless': return None
        
        # 1. Фильтр по стране в названии
        name = unquote(parsed.fragment).lower()
        if not any(k in name for k in TARGET_KEYWORDS):
            return None

        # 2. Фильтр по IP
        host = parsed.hostname
        if not any(host.startswith(p) for p in ALLOWED_IP_PREFIXES):
            return None

        # 3. Проверка порта
        port = int(parsed.port) if parsed.port else 443
        if not is_tcp_reachable(host, port):
            return None

        params = parse_qs(parsed.query)
        return {
            "name": f"Srv-{host}-{port}",
            "server": host,
            "port": port,
            "uuid": parsed.username,
            "sni": params.get('sni', [''])[0],
            "pbk": params.get('pbk', [''])[0],
            "sid": params.get('sid', [''])[0],
            "flow": params.get('flow', [''])[0],
            "type": params.get('type', ['tcp'])[0],
            "fp": params.get('fp', ['chrome'])[0]
        }
    except:
        return None

def build_clash_yaml(proxies):
    """Вручную собирает YAML файл для Clash"""
    lines = ["proxies:"]
    for p in proxies:
        # Формируем строку прокси для Clash (VLESS Reality)
        line = (f"  - {{ name: \"{p['name']}\", type: vless, server: {p['server']}, port: {p['port']}, "
                f"uuid: {p['uuid']}, cipher: auto, tls: true, udp: true, "
                f"servername: {p['sni']}, network: {p['type']}, "
                f"reality-opts: {{ public-key: {p['pbk']}, short-id: {p['sid']} }}, "
                f"client-fingerprint: {p['fp']} }}")
        lines.append(line)

    lines.append("\nproxy-groups:")
    lines.append("  - name: \"🚀 БАЛАНСЕР (Авто-выбор)\"")
    lines.append("    type: url-test")
    lines.append("    url: http://www.gstatic.com/generate_204")
    lines.append("    interval: 300")
    lines.append("    proxies:")
    for p in proxies:
        lines.append(f"      - \"{p['name']}\"")
    
    lines.append("\nrules:")
    lines.append("  - MATCH,🚀 БАЛАНСЕР (Авто-выбор)")
    
    return "\n".join(lines)

def run_git_command(command):
    try: subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except: pass

def main():
    all_links = []
    for url in SOURCE_URLS:
        print(f"Загрузка: {url}")
        try:
            resp = requests.get(url, timeout=15)
            data = decode_base64(resp.text)
            for line in data.splitlines():
                if line.startswith("vless://"):
                    all_links.append(line.strip())
        except: continue

    unique_links = list(dict.fromkeys(all_links))
    print(f"Найдено {len(unique_links)} ссылок. Фильтрация и проверка...")

    valid_proxies = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(parse_vless_to_dict, link) for link in unique_links]
        for future in as_completed(futures):
            res = future.result()
            if res: valid_proxies.append(res)

    if not valid_proxies:
        print("Подходящих серверов не найдено.")
        return

    # Генерируем конфиг
    clash_config = build_clash_yaml(valid_proxies)
    
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(clash_config)
    
    # Git команды
    run_git_command('git config --global user.name "github-actions[bot]"')
    run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
    run_git_command(f'git add {FILE_PATH}')
    run_git_command(f'git commit -m "Update Balancer: {len(valid_proxies)} nodes"')
    run_git_command('git push')
    print(f"✅ Файл обновлен. В балансере {len(valid_proxies)} серверов.")

if __name__ == "__main__":
    main()
