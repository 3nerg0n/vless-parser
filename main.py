import os
import requests
import base64
import time
import subprocess
import socket
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- КОНФИГУРАЦИЯ ---
SOURCE_URLS = [
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/selected.txt",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/merged.txt",
    "https://gitverse.ru/api/repos/bywarm/rser/raw/branch/master/wl.txt",
    "https://gist.github.com/DestroyST6767/50af50221ca1858ba2084efc0f524fbc.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://raw.githubusercontent.com/prominbro/sub/refs/heads/main/212.txt",
    "https://obwl.obprojects.lol/configs/configs.txt",
    "https://obwl.obprojects.lol/configs/selected.txt",
    "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass/bypass-all.txt",
    "https://drive.usercontent.google.com/download?id=1Rl6jIlf2Ula__J9F9nRmCuE6RFdqMTgk&export=download&confirm=t",
    "https://raw.githubusercontent.com/AirLinkVPN1/AirLinkVPN/refs/heads/main/rkn_white_list",
    "https://raw.githubusercontent.com/dequar/deqwl/refs/heads/main/deray.txt",
    "https://gitflic.ru/project/sigil/my-new-cool-project/blob/raw?file=whitelist",
    "https://raw.githubusercontent.com/gergew452/Generation-Liberty/refs/heads/main/githubmirror/best.txt",
    "https://raw.githubusercontent.com/btsk161/Freeinternet_byMygalaru.github.io/refs/heads/main/premium.txt",
    "https://raw.githubusercontent.com/Sanuyyq/sub-storage1/refs/heads/main/bs.txt",
    "https://mifa.world/vless",
    "https://raw.githubusercontent.com/Temnuk/naabuzil/refs/heads/main/whitelist_full",
    "https://raw.githubusercontent.com/ewecrow78-gif/whitelist1/main/list.txt",
    "https://raw.githubusercontent.com/luxxuria/harvester/refs/heads/main/non_ru.txt",
    "https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/ru/vless.txt",
    "https://subrostunnel.vercel.app/gen.txt",
    "https://subrostunnel.vercel.app/wl.txt",
    "https://rostunnel.vercel.app/mega.txt",
    "https://raw.githubusercontent.com/modrinthmodification-create/ownedvpn/main/subscription.txt",
    "https://github.com/ksenkovsolo/HardVPN-bypass-WhiteLists-/raw/refs/heads/main/vpn-lte/WHITELIST-ALL.txt",
    "https://raw.githubusercontent.com/ByeWhiteLists/ByeWhiteLists2/refs/heads/main/ByeWhiteLists2.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-checker-backend/refs/heads/main/checked/RU_Best/ru_white_all_WHITE.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt",
    "https://gitverse.ru/api/repos/nloverx/EtoNeYa_Subs/raw/branch/master/whitelist"
]

FILE_PATH = "sub_vless_3nerg0n_92sh81"
MAX_WORKERS = 40

# --- TELEGRAM CONFIG ---
# Рекомендуется использовать секреты GitHub: os.getenv("TG_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

TARGET_KEYWORDS = ["🇩🇪", "germany", "🇳🇱", "netherlands", "🇫🇮", "finland", "🇸🇪", "sweden"]
ALLOWED_IP_PREFIXES = [
    "217.16", "84.201", "51.250", "78.159", "81.200", "158.160",
    "5.188", "62.152", "109.120", "212.233", "87.239"
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_tcp_latency(host, port, timeout=3):
    """Замеряет время TCP соединения (мс)"""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            end = time.perf_counter()
            return round((end - start) * 1000)
    except:
        return None

def send_to_telegram(config, latency):
    """Безопасная отправка сообщения в Telegram"""
    if not TG_TOKEN or "ВАШ_ТОКЕН" in TG_TOKEN:
        return
    
    text = (
        f"🚀 <b>Найден быстрый конфиг!</b>\n\n"
        f"⏱ <b>Latency:</b> <code>{latency} ms</code>\n"
        f"🔗 <b>Config:</b>\n<code>{config}</code>"
    )
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        # Увеличенный таймаут для запроса к API Telegram
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 429:
            print("Telegram API: Too many requests. Waiting...")
            time.sleep(10)
    except Exception as e:
        print(f"Ошибка отправки в TG: {e}")

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
    """Проверка ссылки: фильтры + замер скорости"""
    try:
        line = line.strip()
        if not line or "://" not in line:
            return None

        parsed = urlparse(line)
        name = unquote(parsed.fragment).lower()
        
        # 1. Фильтр по стране
        if not any(k in name for k in TARGET_KEYWORDS):
            return None

        # 2. Фильтр по IP
        host = parsed.hostname
        if not host or not any(host.startswith(prefix) for prefix in ALLOWED_IP_PREFIXES):
            return None

        # 3. Замер скорости
        port = 443
        try:
            if parsed.port: port = int(parsed.port)
        except: pass
            
        latency = get_tcp_latency(host, port)
        
        if latency is not None:
            return (line, latency)
            
    except:
        pass
    return None

def get_data_with_retry(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.text
        except:
            if i < retries - 1: time.sleep(2)
    return ""

def run_git_command(command):
    try:
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
    except:
        pass

def update_repository(content, count):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    run_git_command('git config --global user.name "github-actions[bot]"')
    run_git_command('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
    run_git_command(f'git add {FILE_PATH}')
    
    status = subprocess.run(f'git status --porcelain {FILE_PATH}', shell=True, capture_output=True, text=True).stdout.strip()
    if not status:
        print("Изменений в файле нет.")
        return

    run_git_command(f'git commit -m "Auto-update: {count} configs with speed test"')
    run_git_command('git push')
    print(f"✅ Репозиторий обновлен: {count} конфигов")

def main():
    raw_links = []
    for url in SOURCE_URLS:
        print(f"Загрузка: {url}")
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
        future_to_link = {executor.submit(check_single_link, link): link for link in unique_raw}
        
        completed = 0
        for future in as_completed(future_to_link):
            result = future.result()
            if result:
                verified_results.append(result)
            
            completed += 1
            if completed % 100 == 0:
                print(f"Прогресс: {completed}/{len(unique_raw)}...")

    if not verified_results:
        print("Подходящих конфигов не найдено.")
        return

    # Сортируем результаты по задержке (от меньшей к большей)
    verified_results.sort(key=lambda x: x[1])

    print(f"Найдено рабочих: {len(verified_results)}. Отправка в Telegram...")
    
    # Отправляем в Telegram последовательно с задержкой
    for link, latency in verified_results:
        send_to_telegram(link, latency)
        time.sleep(1.2) # Задержка, чтобы избежать таймаутов и лимитов

    # Сохраняем только ссылки в файл
    final_content = "\n".join([res[0] for res in verified_results])
    update_repository(final_content, len(verified_results))

if __name__ == "__main__":
    main()
