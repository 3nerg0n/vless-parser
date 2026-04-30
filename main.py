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
MAX_WORKERS = 40 

# Ключевые слова для определения страны в названии
COUNTRY_MAP = {
    "germany": "🇩🇪 Germany",
    "🇩🇪": "🇩🇪 Germany",
    "netherlands": "🇳🇱 Netherlands",
    "🇳🇱": "🇳🇱 Netherlands",
    "finland": "🇫🇮 Finland",
    "🇫🇮": "🇫🇮 Finland"
}

# Ваши префиксы IP (автоматически помечаем как RU)
RU_IP_PREFIXES = [
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
    """Проверка и фильтрация"""
    try:
        line = line.strip()
        if "://" not in line: return None
        
        parsed = urlparse(line)
        host = parsed.hostname
        if not host: return None

        # 1. Проверка по IP префиксам
        is_ru_ip = any(host.startswith(prefix) for prefix in RU_IP_PREFIXES)
        
        # 2. Проверка по названию страны
        name_lower = unquote(parsed.fragment).lower()
        found_country = None
        for key, val in COUNTRY_MAP.items():
            if key in name_lower:
                found_country = val
                break
        
        # Если это не наш целевой IP и в названии нет нужной страны - пропускаем
        if not is_ru_ip and not found_country:
            return None

        # 3. Проверка порта
        port = parsed.port if parsed.port else 443
        if is_tcp_reachable(host, port):
            # Возвращаем кортеж: (сама ссылка, IP хоста, определенная страна)
            # Если IP наш, а страна не нашлась в названии, ставим RU
            final_country = found_country if found_country else "🇷🇺 Russia"
            return (line, host, final_country)
    except:
        pass
    return None

def main():
    raw_links = []
    for url in SOURCE_URLS:
        print(f"Скачивание: {url}")
        data = requests.get(url, headers=HEADERS, timeout=20).text
        if data:
            decoded = decode_base64(data)
            for line in decoded.splitlines():
                if "://" in line: raw_links.append(line)

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} ссылок. Проверка и балансировка...")

    verified_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_link, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res: verified_results.append(res)

    # --- БАЛАНСЕР (Группировка и переименование) ---
    # Используем словарь, чтобы оставить только одну уникальную ссылку на один IP
    unique_ips = {}
    for link, host, country in verified_results:
        if host not in unique_ips:
            unique_ips[host] = (link, country)

    balanced_links = []
    counter = 1
    for host, (link, country) in unique_ips.items():
        # Разбираем ссылку, чтобы заменить фрагмент (название)
        parsed = urlparse(link)
        # Формируем новое имя: "Страна | Balancer #1"
        new_fragment = f"{country} | Balancer #{counter}"
        
        # Собираем ссылку обратно с новым именем
        new_link = urlunparse(parsed._replace(fragment=new_fragment))
        balanced_links.append(new_link)
        counter += 1

    print(f"Готово! После балансировки осталось {len(balanced_links)} уникальных серверов.")

    if balanced_links:
        content = "\n".join(balanced_links)
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        # Здесь можно вызвать вашу функцию update_repository(content, len(balanced_links))
        print(f"Файл {FILE_PATH} обновлен.")

if __name__ == "__main__":
    main()
