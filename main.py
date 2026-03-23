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

# Имя файла подписки для iOS (v2raytun)
IOS_SUB_FILE = "sub_vless_ios"
MAX_WORKERS = 100 

def is_tcp_reachable(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def check_single_link(line):
    """Проверяет ссылку и добавляет теги для iOS"""
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
            
            # Добавляем эмодзи для визуального разделения в v2raytun
            tag = "🌐"
            if any(x in name_low for x in ["de", "germany", "nl", "netherlands"]): tag = "⚡️"
            if any(x in name_low for x in ["us", "usa", "sg", "singapore"]): tag = "🤖"
            if any(x in name_low for x in ["ru", "russia", "fi", "lv"]): tag = "✈️"
            
            # Собираем ссылку обратно с красивым именем
            new_line = line.split('#')[0] + f"#{tag} {name}"
            return new_line
    except:
        pass
    return None

def main():
    raw_links = []
    print("--- Сбор данных для iOS ---")
    for url in SOURCE_URLS:
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
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

    if not verified_links:
        print("Рабочих серверов нет.")
        return

    # Сортируем: сначала Европа и РФ (для скорости), потом всё остальное
    verified_links.sort(key=lambda x: any(c in x.lower() for c in ["⚡️", "✈️"]), reverse=True)

    # Создаем Base64 подписку (именно это нужно для iOS)
    sub_content = "\n".join(verified_links)
    b64_sub = base64.b64encode(sub_content.encode('utf-8')).decode('utf-8')

    with open(IOS_SUB_FILE, "w", encoding="utf-8") as f:
        f.write(b64_sub)

    # Отправка в GitHub
    try:
        subprocess.run('git config --global user.name "github-actions[bot]"', shell=True)
        subprocess.run('git config --global user.email "github-actions[bot]@users.noreply.github.com"', shell=True)
        subprocess.run(f'git add {IOS_SUB_FILE}', shell=True)
        
        status = subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True).stdout.strip()
        if not status: return

        subprocess.run(f'git commit -m "Update iOS Subscription: {len(verified_links)} nodes"', shell=True)
        subprocess.run('git push', shell=True)
        print(f"🚀 Подписка для iOS обновлена!")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
