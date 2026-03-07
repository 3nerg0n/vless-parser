import os
import requests
import base64
import time
import subprocess
from urllib.parse import urlparse, parse_qs, unquote

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
# TOKEN нам больше не нужен для PyGithub, но оставим для совместимости, если он прописан в секретах

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def decode_base64(data):
    data = data.strip()
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8')
    except:
        return data

def parse_vless_links(raw_data):
    decoded_data = decode_base64(raw_data)
    lines = decoded_data.splitlines()
    filtered_links = []
    # Список стран для фильтрации
    target_keywords = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇱🇻", "latvia", "🇫🇮", "finland", "ru", "russia"]

    for line in lines:
        line = line.strip()
        if not line.startswith("vless://"):
            continue
        try:
            parsed = urlparse(line)
            params = parse_qs(parsed.query)
            
            is_tcp = params.get('type', [''])[0].lower() == 'tcp'
            is_reality = params.get('security', [''])[0].lower() == 'reality'
            
            if not (is_tcp and is_reality):
                continue

            name = unquote(parsed.fragment).lower()
            if any(k in name for k in target_keywords):
                filtered_links.append(line)
        except:
            continue
    return filtered_links

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка при скачивании {url} (попытка {i+1}): {e}")
            if i < retries - 1:
                time.sleep(5)
    return ""

def run_git_command(command):
    """Вспомогательная функция для запуска команд git"""
    try:
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка Git: {e.stderr}")
        raise

def update_repository(content, count):
    """Обновление файла через стандартный Git CLI"""
    # 1. Сохраняем файл локально
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Файл сохранен локально ({len(content)} байт). Подготовка к отправке...")

    try:
        # Настройка бота (нужно для коммита)
        run_git_command('git config --global user.name "github-actions[bot]"')
        run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        
        # Добавляем файл в индекс
        run_git_command(f'git add {FILE_PATH}')
        
        # Проверяем, есть ли реальные изменения
        status = subprocess.run(f'git status --porcelain {FILE_PATH}', shell=True, capture_output=True, text=True).stdout.strip()
        if not status:
            print("Изменений нет. Пропускаю обновление.")
            return

        # Коммит и пуш
        run_git_command(f'git commit -m "Auto-update: {count} configs from multiple sources"')
        run_git_command('git push')
        print("✅ Файл успешно обновлен и отправлен в репозиторий!")
        
    except Exception as e:
        print(f"❌ Ошибка при работе с Git: {e}")

def main():
    all_filtered_links = []

    for url in SOURCE_URLS:
        print(f"Обработка источника: {url}")
        raw_data = get_data_with_retry(url)
        if raw_data:
            links = parse_vless_links(raw_data)
            all_filtered_links.extend(links)
            print(f"Найдено подходящих конфигов: {len(links)}")

    unique_links = list(dict.fromkeys(all_filtered_links))
    print(f"Всего уникальных конфигов после фильтрации: {len(unique_links)}")

    if not unique_links:
        print("Конфиги не найдены. Обновление отменено.")
        return

    content = "\n".join(unique_links)
    update_repository(content, len(unique_links))

if __name__ == "__main__":
    main()
