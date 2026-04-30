import os
import requests
import base64
import time
import subprocess
import socket
import yaml # Если в окружении нет PyYAML, можно формировать строку вручную, я сделаю вручную для надежности
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

def parse_vless(link):
    """Парсит vless ссылку в словарь для Clash"""
    try:
        parsed = urlparse(link)
        if parsed.scheme != 'vless': return None
        
        params = parse_qs(parsed.query)
        host = parsed.hostname
        port = int(parsed.port) if parsed.port else 443
        uuid = parsed.username
        
        # Фильтр по IP
        if not any(host.startswith(p) for p in ALLOWED_IP_PREFIXES):
            # Если IP не в списке, проверяем страну в названии
            name = unquote(parsed.fragment).lower()
            if not any(k in name for k in TARGET_KEYWORDS):
                return None

        # Проверка доступности
        if not is_tcp_reachable(host, port):
            return None

        # Формируем структуру для Clash
        config = {
            "name": f"Srv-{host}-{port}-" + str(time.time())[-4:],
            "type": "vless",
            "server": host,
            "port": port,
            "uuid": uuid,
            "cipher": "auto",
            "tls": params.get('security', [''])[0] == 'reality',
            "servername": params.get('sni', [''])[0],
            "network": params.get('type', ['tcp'])[0],
            "reality-opts": {
                "public-key": params.get('pbk', [''])[0],
                "short-id": params.get('sid', [''])[0]
            },
            "client-fingerprint": params.get('fp', ['chrome'])[0]
        }
        return config
    except:
        return None

def generate_clash_yaml(proxies):
    """Создает текст конфига Clash с балансировщиком"""
    proxy_names = [p['name'] for p in proxies]
    
    yaml_text = "proxies:\n"
    for p in proxies:
        yaml_text += f"  - {{ name: \"{p['name']}\", type: vless, server: {p['server']}, port: {p['port']}, uuid: {p['uuid']}, cipher: auto, tls: true, servername: {p['servername']}, network: {p['network']}, reality-opts: {{ public-key: {p['reality-opts']['public-key']}, short-id: {p['reality-opts']['short-id']} }}, client-fingerprint: {p['client-fingerprint']} }}\n"

    yaml_text += "\nproxy-groups:\n"
    # Группа авто-выбора (URL-Test) - это и есть твой балансер
    yaml_text += "  - name: \"🚀 БАЛАНСЕР (Авто-выбор)\"\n"
    yaml_text += "    type: url-test\n"
    yaml_text += "    url: http://www.gstatic.com/generate_204\n"
    yaml_text += "    interval: 300\n"
    yaml_text += "    proxies:\n"
    for name in proxy_names:
        yaml_text += f"      - \"{name}\"\n"
    
    yaml_text += "\nrules:\n  - MATCH,🚀 БАЛАНСЕР (Авто-выбор)\n"
    return yaml_text

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
    print(f"Найдено {len(unique_links)} ссылок. Проверка...")

    valid_proxies = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(parse_vless, link) for link in unique_links]
        for future in as_completed(futures):
            res = future.result()
            if res: valid_proxies.append(res)

    if not valid_proxies:
        print("Нет рабочих серверов.")
        return

    # Генерируем Clash конфиг
    clash_config = generate_clash_yaml(valid_proxies)
    
    # Сохраняем
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(clash_config)
    
    # Пушим в репозиторий
    run_git_command('git config --global user.name "github-actions[bot]"')
    run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
    run_git_command(f'git add {FILE_PATH}')
    run_git_command(f'git commit -m "Update Balancer: {len(valid_proxies)} nodes"')
    run_git_command('git push')
    print(f"✅ Балансер обновлен! Серверов внутри: {len(valid_proxies)}")

if __name__ == "__main__":
    main()
