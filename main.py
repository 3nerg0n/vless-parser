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
# Это файл вашей подписки (одна ссылка для приложения)
FILE_PATH = "sub_vless_3nerg0n_92sh81" 
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
        
        # Фильтруем только Reality
        if params.get('security', [''])[0].lower() != 'reality':
            return None

        host = parsed.hostname
        port = int(parsed.port) if parsed.port else 443
        
        if is_tcp_reachable(host, port):
            # Добавляем метку в название для удобства балансировки
            name = unquote(parsed.fragment)
            # Если сервер из нужных нам стран, помечаем его
            tag = ""
            name_low = name.lower()
            if any(x in name_low for x in ["de", "nl", "fi", "ru"]): tag = "🚀"
            if any(x in name_low for x in ["us", "sg"]): tag = "🤖"
            
            new_line = line.split('#')[0] + f"#{tag}{name}"
            return new_line
    except:
        pass
    return None

def update_repository(content, count):
    # Кодируем в Base64, чтобы приложение восприняло это как единую подписку
    b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(b64_content)
    
    try:
        subprocess.run('git config --global user.name "github-actions[bot]"', shell=True)
        subprocess.run('git config --global user.email "github-actions[bot]@users.noreply.github.com"', shell=True)
        subprocess.run(f'git add {FILE_PATH}', shell=True)
        subprocess.run(f'git commit -m "Update Super-Subscription: {count} live nodes"', shell=True)
        subprocess.run('git push', shell=True)
        print(f"✅ Подписка обновлена: {count} серверов")
    except:
        pass

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
        # Сортируем: сначала самые быстрые (Германия, Нидерланды)
        verified_links.sort(key=lambda x: "🚀" not in x)
        update_repository("\n".join(verified_links), len(verified_links))

if __name__ == "__main__":
    main()
