import os
import requests
import base64
import time
import json
import subprocess
import socket
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- НАСТРОЙКИ ---
SOURCE_URLS = ["https://etoneya.a9fm.site/1", "https://etoneya.a9fm.site/2"]
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

# Ссылки для проверки доступа
TEST_TIKTOK = "https://www.tiktok.com"
TEST_GOOGLE_AI = "https://aistudio.google.com"

def install_xray():
    """Скачивает ядро Xray для тестов"""
    print("Установка Xray core...")
    url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
    os.system(f"curl -L -o xray.zip {url} && unzip -o xray.zip xray && chmod +x xray")

def create_xray_config(vless_link):
    """Создает временный конфиг для Xray из VLESS ссылки"""
    try:
        parsed = urlparse(vless_link)
        params = parse_qs(parsed.query)
        user_info = parsed.netloc.split('@')
        uuid = user_info[0]
        host_port = user_info[1].split(':')
        address = host_port[0]
        port = int(host_port[1])

        config = {
            "inbounds": [{"port": 10808, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": address, "port": port,
                        "users": [{"id": uuid, "encryption": "none"}]
                    }]
                },
                "streamSettings": {
                    "network": params.get('type', ['tcp'])[0],
                    "security": params.get('security', ['none'])[0],
                    "realitySettings": {
                        "serverName": params.get('sni', [''])[0],
                        "publicKey": params.get('pbk', [''])[0],
                        "shortId": params.get('sid', [''])[0],
                        "spiderX": params.get('spx', [''])[0]
                    }
                }
            }]
        }
        with open('test_config.json', 'w') as f:
            json.dump(config, f)
        return True
    except:
        return False

def test_connectivity(vless_link):
    """Проверяет доступ к сервисам через VLESS"""
    results = {"tiktok": False, "google_ai": False, "ping": 999}
    
    if not create_xray_config(vless_link):
        return results

    # Запускаем Xray в фоне
    process = subprocess.Popen(["./xray", "-c", "test_config.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2) # Ждем инициализации

    proxies = {"http": "socks5h://127.0.0.1:10808", "https": "socks5h://127.0.0.1:10808"}
    
    try:
        # Тест TikTok
        r_tk = requests.get(TEST_TIKTOK, proxies=proxies, timeout=10)
        if r_tk.status_code == 200: results["tiktok"] = True
        
        # Тест Google AI
        r_ai = requests.get(TEST_GOOGLE_AI, proxies=proxies, timeout=10)
        if r_ai.status_code == 200: results["google_ai"] = True
        
        print(f"Результаты: TikTok={results['tiktok']}, GoogleAI={results['google_ai']}")
    except:
        pass

    process.terminate()
    return results

def parse_vless_links(raw_data):
    try:
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data
    
    lines = decoded_data.splitlines()
    filtered = []
    keywords = ["germany", "netherlands", "nederland", "🇩🇪", "🇳🇱"]
    
    for line in lines:
        line = line.strip()
        if line.startswith("vless://"):
            name = unquote(urlparse(line).fragment).lower()
            if any(k in name for k in keywords):
                filtered.append(line)
    return list(dict.fromkeys(filtered))

def update_github():
    install_xray()
    all_links = []
    for url in SOURCE_URLS:
        try:
            r = requests.get(url, timeout=20)
            all_links.extend(parse_vless_links(r.text))
        except: continue
    
    unique_links = list(dict.fromkeys(all_links))
    
    tiktok_links = []
    google_ai_links = []
    working_links = []

    print(f"Начинаем проверку {len(unique_links)} серверов...")
    for link in unique_links:
        print(f"Тестируем: {unquote(urlparse(link).fragment)}")
        res = test_connectivity(link)
        
        # Если хоть один тест прошел, считаем сервер живым
        if res["tiktok"] or res["google_ai"]:
            working_links.append(link)
            if res["tiktok"]: tiktok_links.append(link)
            if res["google_ai"]: google_ai_links.append(link)

    # Сохранение файлов
    files_to_update = {
        "config": "\n".join(working_links),
        "config_tiktok": "\n".join(tiktok_links),
        "config_google_ai": "\n".join(google_ai_links)
    }

    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    for path, content in files_to_update.items():
        try:
            curr = repo.get_contents(path)
            repo.update_file(path, f"Update {path}", content, curr.sha)
        except:
            repo.create_file(path, f"Create {path}", content)

if __name__ == "__main__":
    update_github()
