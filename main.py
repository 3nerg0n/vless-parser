import os
import requests
import base64
import time
import subprocess
import socket
from urllib.parse import urlparse, parse_qs, unquote, quote
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
MAX_WORKERS = 25

# Словарь для красивого именования стран
COUNTRY_MAP = {
    "germany": "🇩🇪 Germany", "🇩🇪": "🇩🇪 Germany",
    "netherlands": "🇳🇱 Netherlands", "🇳🇱": "🇳🇱 Netherlands",
    "latvia": "🇱🇻 Latvia", "🇱🇻": "🇱🇻 Latvia",
    "finland": "🇫🇮 Finland", "🇫🇮": "🇫🇮 Finland",
    "russia": "🇷🇺 Russia", "ru": "🇷🇺 Russia"
}

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
    if data.startswith("vless://"): return data
    try:
        missing_padding = len(data) % 4
        if missing_padding: data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except:
        return data

def check_single_link(line):
    """Проверка доступности и фильтрация"""
    try:
        parsed = urlparse(line)
        params = parse_qs(parsed.query)
        
        is_tcp = params.get('type', [''])[0].lower() == 'tcp'
        is_reality = params.get('security', [''])[0].lower() == 'reality'
        
        if not (is_tcp and is_reality):
            return None

        name = unquote(parsed.fragment).lower()
        # Проверяем наличие ключевых слов стран
        if any(k in name for k in COUNTRY_MAP.keys()):
            host = parsed.hostname
            port = int(parsed.port) if parsed.port else 443
            if is_tcp_reachable(host, port):
                return line
    except:
        pass
    return None

def rename_link(line, index):
    """Переименовывает ссылку в формат: Число | Флаг Страна | SNI"""
    try:
        parsed = urlparse(line)
        params = parse_qs(parsed.query)
        sni = params.get('sni', [''])[0]
        old_name = unquote(parsed.fragment).lower()

        # Определяем страну
        country_str = "🌐 Unknown"
        for key, val in COUNTRY_MAP.items():
            if key in old_name:
                country_str = val
                break
        
        # Формируем новое имя: "1 | 🇩🇪 Germany | sni.com"
        new_name = f"{index} | {country_str}"
        if sni:
            new_name += f" | {sni}"
        
        # Собираем URL обратно с новым фрагментом
        new_parsed = parsed._replace(fragment=quote(new_name))
        return new_parsed.geturl()
    except:
        return line

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.text
        except:
            time.sleep(2)
    return ""

def run_git_command(command):
    subprocess.run(command, check=True, shell=True, capture_output=True, text=True)

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
        run_git_command(f'git commit -m "Auto-update: {count} verified links"')
        run_git_command('git push')
        print(f"✅ Успешно обновлено: {count} конфигов")
    except Exception as e:
        print(f"❌ Ошибка Git: {e}")

def main():
    raw_links = []
    stats = {}

    print("--- Сбор данных ---")
    for url in SOURCE_URLS:
        print(f"Загрузка: {url}...", end=" ", flush=True)
        data = get_data_with_retry(url)
        count = 0
        if data:
            decoded = decode_base64(data)
            for line in decoded.splitlines():
                line = line.strip()
                if line.startswith("vless://"):
                    raw_links.append(line)
                    count += 1
            print(f"найдено {count}")
        else:
            print("ошибка")
        stats[url] = count

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"\nУникальных ссылок: {len(unique_raw)}. Проверка...")

    verified_raw = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_link, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res: verified_raw.append(res)

    # Сортируем или просто переименовываем с нумерацией
    final_links = []
    for i, link in enumerate(verified_raw, start=1):
        renamed = rename_link(link, i)
        final_links.append(renamed)

    print(f"Живых конфигов: {len(final_links)}")

    if final_links:
        update_repository("\n".join(final_links), len(final_links))
    else:
        print("Ничего не найдено.")

if __name__ == "__main__":
    main()
