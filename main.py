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

# Ключевые слова для определения страны
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

# Ваши префиксы IP
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

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.text
        except:
            if i < retries - 1:
                time.sleep(2)
    return ""

def check_single_link(line):
    """Проверка: Страна -> IP -> Доступность"""
    try:
        line = line.strip()
        if "://" not in line: return None
        
        parsed = urlparse(line)
        host = parsed.hostname
        if not host: return None

        # 1. Определяем страну по названию
        name_lower = unquote(parsed.fragment).lower()
        found_country = None
        for key, val in COUNTRY_MAP.items():
            if key in name_lower:
                found_country = val
                break
        
        # 2. Проверяем IP префикс
        is_allowed_ip = any(host.startswith(prefix) for prefix in ALLOWED_IP_PREFIXES)
        
        # Если страна не подошла И IP не из списка — отбрасываем
        if not found_country and not is_allowed_ip:
            return None

        # 3. Проверка порта
        port = parsed.port if parsed.port else 443
        if is_tcp_reachable(host, port):
            # Если IP наш, а страна в названии не указана, помечаем как Russia
            final_label = found_country if found_country else "🇷🇺 Russia"
            return (line, host, final_label)
    except:
        pass
    return None

def run_git_command(command):
    try:
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка Git: {e.stderr}")

def update_repository(content, count):
    """Запись в файл и пуш в репозиторий"""
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    try:
        run_git_command('git config --global user.name "github-actions[bot]"')
        run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        run_git_command(f'git add {FILE_PATH}')
        
        # Проверка изменений
        status = subprocess.run(f'git status --porcelain {FILE_PATH}', shell=True, capture_output=True, text=True).stdout.strip()
        if not status:
            print("Изменений в файле нет, пуш не требуется.")
            return

        run_git_command(f'git commit -m "Auto-update: {count} balanced configs"')
        run_git_command('git push')
        print(f"✅ Успешно обновлено и отправлено: {count} конфигов")
    except Exception as e:
        print(f"❌ Ошибка при обновлении репозитория: {e}")

def main():
    raw_links = []
    for url in SOURCE_URLS:
        print(f"Скачивание: {url}")
        data = get_data_with_retry(url)
        if data:
            decoded = decode_base64(data)
            for line in decoded.splitlines():
                if "://" in line:
                    raw_links.append(line.strip())

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} уникальных ссылок. Начинаю проверку...")

    verified_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_link, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res:
                verified_results.append(res)

    # --- БАЛАНСЕР (Дедупликация по IP и переименование) ---
    unique_ips = {}
    for link, host, label in verified_results:
        if host not in unique_ips:
            unique_ips[host] = (link, label)

    balanced_links = []
    counter = 1
    for host, (link, label) in unique_ips.items():
        parsed = urlparse(link)
        # Создаем новое имя для балансера
        new_name = f"{label} | Balancer #{counter}"
        # Собираем ссылку обратно с новым фрагментом
        new_link = urlunparse(parsed._replace(fragment=new_name))
        balanced_links.append(new_link)
        counter += 1

    print(f"Фильтрация завершена. Живых уникальных серверов: {len(balanced_links)}")

    if not balanced_links:
        print("Нет конфигов для записи.")
        return

    # Записываем и пушим
    final_content = "\n".join(balanced_links)
    update_repository(final_content, len(balanced_links))

if __name__ == "__main__":
    main()
