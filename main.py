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

FILE_PATH = "sub_streisand" 
MAX_WORKERS = 100 

def is_tcp_reachable(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def check_single_link(line):
    try:
        parsed = urlparse(line)
        params = parse_qs(parsed.query)
        
        if params.get('security', [''])[0].lower() != 'reality':
            return None

        host = parsed.hostname
        port = int(parsed.port) if parsed.port else 443
        
        if is_tcp_reachable(host, port):
            name = unquote(parsed.fragment)
            name_low = name.lower()
            
            # Добавляем теги для маршрутизации в Streisand
            tag = "[GEN]"
            if any(x in name_low for x in ["de", "germany", "nl", "netherlands", "fi", "ru"]): tag = "[YT-TG]"
            if any(x in name_low for x in ["us", "usa", "sg", "singapore"]): tag = "[AI]"
            
            # Собираем ссылку с тегом в начале названия
            new_line = line.split('#')[0] + f"#{tag} {name}"
            return new_line
    except:
        pass
    return None

def main():
    raw_links = []
    for url in SOURCE_URLS:
        try:
            res = requests.get(url, timeout=15)
            data = res.text
            if "vless://" not in data:
                try: data = base64.b64decode(data).decode('utf-8')
                except: pass
            for line in data.splitlines():
                if line.strip().startswith("vless://"):
                    raw_links.append(line.strip())
        except: continue

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} ссылок. Проверка...")

    verified_links = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_link, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res: verified_links.append(res)

    if verified_links:
        # Создаем Base64 строку (стандарт подписки)
        sub_content = "\n".join(verified_links)
        b64_sub = base64.b64encode(sub_content.encode('utf-8')).decode('utf-8')

        with open(FILE_PATH, "w", encoding="utf-8") as f:
            f.write(b64_sub)

        try:
            subprocess.run('git config --global user.name "github-actions[bot]"', shell=True)
            subprocess.run('git config --global user.email "github-actions[bot]@users.noreply.github.com"', shell=True)
            subprocess.run(f'git add {FILE_PATH}', shell=True)
            subprocess.run(f'git commit -m "Update Streisand Sub: {len(verified_links)} nodes"', shell=True)
            subprocess.run('git push', shell=True)
            print("✅ Подписка для Streisand обновлена!")
        except: pass

if __name__ == "__main__":
    main()
