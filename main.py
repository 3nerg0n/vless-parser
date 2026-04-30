import os
import requests
import base64
import time
import subprocess
import socket
from urllib.parse import urlparse, parse_qs, unquote, urlunparse
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

# Ключевые слова стран для фильтрации и именования
COUNTRY_MAP = {
    "germany": "🇩🇪 Germany",
    "🇩🇪": "🇩🇪 Germany",
    "netherlands": "🇳🇱 Netherlands",
    "🇳🇱": "🇳🇱 Netherlands",
    "finland": "🇫🇮 Finland",
    "🇫🇮": "🇫🇮 Finland",
    "russia": "🇷🇺 Russia",
    "ru": "🇷🇺 Russia",
    "🇷🇺": "🇷🇺 Russia"
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
        if "://" in data: return data
        missing_padding = len(data) % 4
        if missing_padding: data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except: return data

def check_and_format_link(line):
    """Проверяет фильтры и возвращает кортеж (ссылка, хост, страна)"""
    try:
        line = line.strip()
        if "://" not in line: return None
        
        parsed = urlparse(line)
        host = parsed.hostname
        if not host: return None

        # 1. Фильтр по стране в названии
        name_lower = unquote(parsed.fragment).lower()
        found_country = None
        for key, val in COUNTRY_MAP.items():
            if key in name_lower:
                found_country = val
                break
        
        # 2. Фильтр по IP
        is_allowed_ip = any(host.startswith(p) for p in ALLOWED_IP_PREFIXES)

        # Если не подошла страна И не подошел IP — отбрасываем
        if not found_country and not is_allowed_ip:
            return None

        # 3. Проверка порта
        port = int(parsed.port) if parsed.port else 443
        if is_tcp_reachable(host, port):
            # Если IP наш, а страна не определена — ставим Russia
            label = found_country if found_country else "🇷🇺 Russia"
            return (line, host, label)
    except:
        pass
    return None

def run_git_command(command):
    try: subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except: pass

def main():
    all_raw_links = []
    for url in SOURCE_URLS:
        print(f"Загрузка: {url}")
        try:
            resp = requests.get(url, timeout=15)
            data = decode_base64(resp.text)
            for line in data.splitlines():
                if "://" in line:
                    all_raw_links.append(line.strip())
        except: continue

    unique_links = list(dict.fromkeys(all_raw_links))
    print(f"Найдено {len(unique_links)} ссылок. Проверка...")

    valid_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_and_format_link, link) for link in unique_links]
        for future in as_completed(futures):
            res = future.result()
            if res: valid_results.append(res)

    if not valid_results:
        print("Рабочих серверов не найдено.")
        return

    # Группировка (Балансировка): оставляем уникальные IP и переименовываем
    unique_ips = {}
    for link, host, label in valid_results:
        if host not in unique_ips:
            unique_ips[host] = (link, label)

    final_links = []
    counter = 1
    for host, (link, label) in unique_ips.items():
        parsed = urlparse(link)
        # Создаем красивое имя для балансера
        new_fragment = f"{label} | Balancer #{counter}"
        # Собираем ссылку обратно
        new_link = urlunparse(parsed._replace(fragment=new_fragment))
        final_links.append(new_link)
        counter += 1

    # --- СЕКРЕТ УСПЕХА ДЛЯ STREISAND ---
    # Объединяем все ссылки через новую строку и кодируем ВЕСЬ файл в Base64
    sub_content = "\n".join(final_links)
    encoded_sub = base64.b64encode(sub_content.encode('utf-8')).decode('utf-8')

    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(encoded_sub)
    
    # Отправка в репозиторий
    run_git_command('git config --global user.name "github-actions[bot]"')
    run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
    run_git_command(f'git add {FILE_PATH}')
    run_git_command(f'git commit -m "Update Balancer Sub: {len(final_links)} nodes"')
    run_git_command('git push')
    print(f"✅ Подписка обновлена! Добавлено {len(final_links)} серверов.")

if __name__ == "__main__":
    main()
