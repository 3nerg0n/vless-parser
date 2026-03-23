import os
import requests
import base64
import time
import subprocess
import socket
import json  # Добавлено для балансировщика
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- КОНФИГУРАЦИЯ ---
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
FILE_PATH = "sub_vless_3nerg0n_92sh81" 
BALANCER_PATH = "smart_balancer.json"  # Файл супер-сервера
MAX_WORKERS = 50  # Увеличил для скорости

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def is_tcp_reachable(host, port, timeout=2):
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
    try:
        parsed = urlparse(line)
        params = parse_qs(parsed.query)
        is_tcp = params.get('type', [''])[0].lower() == 'tcp'
        is_reality = params.get('security', [''])[0].lower() == 'reality'
        if not (is_tcp and is_reality):
            return None
        target_keywords = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇱🇻", "latvia", "🇫🇮", "finland", "RU", "russia"]
        name = unquote(parsed.fragment).lower()
        if any(k in name for k in target_keywords):
            host = parsed.hostname
            port = int(parsed.port) if parsed.port else 443
            if is_tcp_reachable(host, port):
                return line
    except:
        pass
    return None

# --- НОВАЯ ФУНКЦИЯ: ПАРСИНГ ДЛЯ JSON ---
def vless_to_outbound(link):
    try:
        p = urlparse(link)
        qs = parse_qs(p.query)
        return {
            "type": "vless",
            "tag": unquote(p.fragment) or p.hostname,
            "server": p.hostname,
            "server_port": int(p.port) if p.port else 443,
            "uuid": p.username,
            "packet_encoding": "xudp",
            "tls": {
                "enabled": True,
                "server_name": qs.get('sni', [''])[0],
                "utls": {"enabled": True, "fingerprint": qs.get('fp', ['chrome'])[0]},
                "reality": {
                    "enabled": True,
                    "public_key": qs.get('pbk', [''])[0],
                    "short_id": qs.get('sid', [''])[0]
                }
            }
        }
    except: return None

# --- НОВАЯ ФУНКЦИЯ: СОЗДАНИЕ БАЛАНСИРОВЩИКА ---
def create_balancer(links):
    outbounds = []
    for l in links:
        obj = vless_to_outbound(l)
        if obj: outbounds.append(obj)
    
    if not outbounds: return None
    
    tags = [o["tag"] for o in outbounds]
    
    config = {
        "outbounds": [
            {
                "type": "urltest",
                "tag": "🚀 SUPER-BALANCER (AUTO)",
                "outbounds": tags,
                "interval": "1m"
            }
        ] + outbounds,
        "route": {
            "rules": [
                {"domain_suffix": ["youtube.com", "googlevideo.com", "openai.com", "anthropic.com", "chatgpt.com", "t.me", "telegram.org"], "outbound": "🚀 SUPER-BALANCER (AUTO)"}
            ],
            "final": "🚀 SUPER-BALANCER (AUTO)"
        }
    }
    return json.dumps(config, indent=2, ensure_ascii=False)

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if i < retries - 1:
                time.sleep(5)
    return ""

def run_git_command(command):
    try:
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка Git: {e.stderr}")
        raise

def update_repository(content, balancer_content, count):
    # Сохраняем обычный список
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    # Сохраняем балансировщик
    if balancer_content:
        with open(BALANCER_PATH, "w", encoding="utf-8") as f:
            f.write(balancer_content)
    
    try:
        run_git_command('git config --global user.name "github-actions[bot]"')
        run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        run_git_command(f'git add {FILE_PATH} {BALANCER_PATH}')
        
        status = subprocess.run(f'git status --porcelain', shell=True, capture_output=True, text=True).stdout.strip()
        if not status:
            print("Изменений нет.")
            return

        run_git_command(f'git commit -m "Update: {count} links + Smart Balancer"')
        run_git_command('git push')
        print(f"✅ Успешно обновлено!")
    except Exception as e:
        print(f"❌ Ошибка Git: {e}")

def main():
    raw_links = []
    for url in SOURCE_URLS:
        print(f"Скачивание: {url}")
        data = get_data_with_retry(url)
        if data:
            if "vless://" not in data:
                try: data = decode_base64(data)
                except: pass
            for line in data.splitlines():
                line = line.strip()
                if line.startswith("vless://"):
                    raw_links.append(line)

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} уникальных ссылок. Проверка...")

    verified_links = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_link = {executor.submit(check_single_link, link): link for link in unique_raw}
        for future in as_completed(future_to_link):
            result = future.result()
            if result: verified_links.append(result)

    if not verified_links:
        print("Нет рабочих конфигов.")
        return

    content = "\n".join(verified_links)
    balancer_json = create_balancer(verified_links) # Создаем JSON
    
    update_repository(content, balancer_json, len(verified_links))

if __name__ == "__main__":
    main()
