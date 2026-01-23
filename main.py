import os
import requests
import base64
import time
import json
import subprocess
import re
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor
from github import Github

# --- НАСТРОЙКИ ---
SOURCE_URLS = ["https://etoneya.a9fm.site/1", "https://etoneya.a9fm.site/2"]
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")
MAX_THREADS = 15 

def install_xray():
    if not os.path.exists("./xray"):
        url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
        os.system(f"curl -L -o xray.zip {url} && unzip -o xray.zip xray && chmod +x xray")

def check_server(vless_link, index):
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
        time.sleep(2)
        proxies = {"http": f"socks5h://127.0.0.1:{port}", "https": f"socks5h://127.0.0.1:{port}"}
        res = {"link": vless_link, "tiktok": False, "google_ai": False}
        try:
            r = requests.get("https://cp.cloudflare.com/generate_204", proxies=proxies, timeout=5)
            if r.status_code == 204:
                res["tiktok"] = True 
                try:
                    r_ai = requests.get("https://aistudio.google.com", proxies=proxies, timeout=7)
                    if r_ai.status_code == 200: res["google_ai"] = True
                except: pass
        except: pass
        proc.terminate()
        if os.path.exists(config_path): os.remove(config_path)
        return res
    except: return None

def update_github():
    install_xray()
    all_raw_links = []
    reality_count = 0
    
    for url in SOURCE_URLS:
        try:
            r = requests.get(url, timeout=15)
            text = r.text
            if "vless://" not in text:
                try: text = base64.b64decode(text.strip()).decode('utf-8')
                except: pass
            
            found = re.findall(r'(vless://[^\s]+)', text)
            print(f"🔎 Источник {url}: найдено {len(found)} ссылок")
            
            for link in found:
                # Считаем сколько вообще Reality ссылок
                if "security=reality" in link:
                    reality_count += 1
                    name = unquote(urlparse(link).fragment).lower()
                    
                    # Более гибкий поиск стран
                    # Ищем полные названия или коды DE/NL как отдельные слова
                    keywords = ["germany", "netherlands", "nederland", "🇩🇪", "🇳🇱"]
                    iso_codes = ["de", "nl"]
                    
                    has_loc = any(k in name for k in keywords)
                    if not has_loc:
                        # Разбиваем имя на слова и ищем точное совпадение de или nl
                        words = re.split(r'[^a-z]', name)
                        if any(code in words for code in iso_codes):
                            has_loc = True
                    
                    if has_loc:
                        all_raw_links.append(link)
        except: continue

    unique_links = list(dict.fromkeys(all_raw_links))
    print(f"📊 Всего Reality-ссылок во всех локациях: {reality_count}")
    print(f"🚀 Итого к проверке (DE/NL + Reality): {len(unique_links)}")

    if not unique_links:
        print("⚠️ Подходящих ссылок не найдено. Возможно, сейчас нет Reality-серверов для DE/NL.")
        return

    google_ai_list, tiktok_list = [], []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        results = list(executor.map(check_server, unique_links, range(len(unique_links))))

    for r in results:
        if r:
            if r["google_ai"]: google_ai_list.append(r["link"])
            elif r["tiktok"]: tiktok_list.append(r["link"])

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
