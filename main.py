import os
import requests
import base64
import time
import json
import subprocess
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor
from github import Github

# --- НАСТРОЙКИ ---
SOURCE_URLS = ["https://etoneya.a9fm.site/1", "https://etoneya.a9fm.site/2"]
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")
MAX_THREADS = 15  # Сколько серверов проверять одновременно

def install_xray():
    if not os.path.exists("./xray"):
        url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
        os.system(f"curl -L -o xray.zip {url} && unzip -o xray.zip xray && chmod +x xray")

def check_server(vless_link, index):
    """Функция проверки одного сервера (запускается в отдельном потоке)"""
    port = 10000 + index
    config_path = f"config_{port}.json"
    
    try:
        parsed = urlparse(vless_link)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        user_info = parsed.netloc.split('@')
        uuid, hp = user_info[0], user_info[1].split(':')
        
        config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": port, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{
                "protocol": "vless",
                "settings": {"vnext": [{"address": hp[0], "port": int(hp[1]), "users": [{"id": uuid, "encryption": "none", "flow": params.get('flow', '')}]}]},
                "streamSettings": {
                    "network": params.get('type', 'tcp'),
                    "security": params.get('security', 'none'),
                    "realitySettings": {"fingerprint": params.get('fp', 'chrome'), "serverName": params.get('sni', ''), "publicKey": params.get('pbk', ''), "shortId": params.get('sid', '')}
                }
            }]
        }
        
        with open(config_path, 'w') as f: json.dump(config, f)
        
        proc = subprocess.Popen(["./xray", "-c", config_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) # Короткая пауза для запуска

        proxies = {"http": f"socks5h://127.0.0.1:{port}", "https": f"socks5h://127.0.0.1:{port}"}
        res = {"link": vless_link, "tiktok": False, "google_ai": False}

        # 1. Быстрая проверка на "живучесть" (Cloudflare)
        try:
            r = requests.get("https://cp.cloudflare.com/generate_204", proxies=proxies, timeout=5)
            if r.status_code == 204:
                res["tiktok"] = True # Если живой в DE/NL - считаем что TikTok ок
                
                # 2. Проверка Google AI
                try:
                    r_ai = requests.get("https://aistudio.google.com", proxies=proxies, timeout=7)
                    if r_ai.status_code == 200:
                        res["google_ai"] = True
                except: pass
        except: pass

        proc.terminate()
        if os.path.exists(config_path): os.remove(config_path)
        return res
    except:
        return None

def update_github():
    install_xray()
    all_raw_links = []
    for url in SOURCE_URLS:
        try:
            r = requests.get(url, timeout=15)
            decoded = base64.b64decode(r.text.strip()).decode('utf-8') if not r.text.startswith("vless") else r.text
            for line in decoded.splitlines():
                if "vless://" in line and "security=reality" in line:
                    name = unquote(urlparse(line).fragment).lower()
                    if any(k in name for k in ["germany", "netherlands"]):
                        all_raw_links.append(line)
        except: continue

    unique_links = list(dict.fromkeys(all_raw_links))
    print(f"🔍 Найдено {len(unique_links)} серверов. Начинаем параллельную проверку...")

    google_ai_list = []
    tiktok_list = []

    # Запуск многопоточности
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        results = list(executor.map(check_server, unique_links, range(len(unique_links))))

    for r in results:
        if r:
            if r["google_ai"]:
                google_ai_list.append(r["link"])
            elif r["tiktok"]: # Если не попал в Google AI, но живой
                tiktok_list.append(r["link"])

    # Сохранение
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    for path, links in [("config_google_ai", google_ai_list), ("config_tiktok", tiktok_list)]:
        content = "\n".join(links)
        try:
            curr = repo.get_contents(path)
            repo.update_file(path, f"Update {path}", content, curr.sha)
        except:
            repo.create_file(path, f"Create {path}", content)
    
    print(f"✅ Готово! Google AI: {len(google_ai_list)}, TikTok: {len(tiktok_list)}")

if __name__ == "__main__":
    update_github()
