import os
import requests
import base64
import time
import json
import subprocess
from urllib.parse import urlparse, parse_qs, unquote
from github import Github

# --- НАСТРОЙКИ ---
SOURCE_URLS = ["https://etoneya.a9fm.site/1", "https://etoneya.a9fm.site/2"]
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
TOKEN = os.getenv("MY_GITHUB_TOKEN")

def install_xray():
    if not os.path.exists("./xray"):
        print("📥 Установка Xray core...")
        url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
        os.system(f"curl -L -o xray.zip {url} && unzip -o xray.zip xray && chmod +x xray")
    else:
        print("✅ Xray уже установлен")

def create_xray_config(vless_link):
    try:
        parsed = urlparse(vless_link)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        user_info = parsed.netloc.split('@')
        uuid = user_info[0]
        host_port = user_info[1].split(':')
        address = host_port[0]
        port = int(host_port[1])

        config = {
            "log": {"loglevel": "warning"}, # Включили логи для отладки
            "inbounds": [{
                "port": 10808,
                "protocol": "socks",
                "settings": {"udp": True},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]}
            }],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": address, "port": port,
                        "users": [{
                            "id": uuid, 
                            "encryption": "none",
                            "flow": params.get('flow', '')
                        }]
                    }]
                },
                "streamSettings": {
                    "network": params.get('type', 'tcp'),
                    "security": params.get('security', 'none'),
                    "realitySettings": {
                        "fingerprint": params.get('fp', 'chrome'),
                        "serverName": params.get('sni', ''),
                        "publicKey": params.get('pbk', ''),
                        "shortId": params.get('sid', ''),
                        "spiderX": params.get('spx', '/')
                    }
                }
            }]
        }
        with open('test_config.json', 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return False

def test_connectivity(vless_link):
    results = {"tiktok": False, "google_ai": False}
    if not create_xray_config(vless_link):
        return results

    # Запускаем Xray и ловим его ошибки
    log_file = open("xray_error.log", "w")
    process = subprocess.Popen(
        ["./xray", "-c", "test_config.json"], 
        stdout=log_file, 
        stderr=log_file
    )
    
    time.sleep(5) # Ждем инициализации

    proxies = {"http": "socks5h://127.0.0.1:10808", "https": "socks5h://127.0.0.1:10808"}
    
    try:
        # Сначала проверим просто доступ к сети (Cloudflare)
        requests.get("https://1.1.1.1", proxies=proxies, timeout=10)
        
        # Если сеть есть, проверяем сервисы
        try:
            r_tk = requests.get("https://www.tiktok.com", proxies=proxies, timeout=10)
            if r_tk.status_code == 200: results["tiktok"] = True
        except: pass

        try:
            r_ai = requests.get("https://aistudio.google.com", proxies=proxies, timeout=10)
            if r_ai.status_code == 200: results["google_ai"] = True
        except: pass
    except Exception as e:
        # Если даже 1.1.1.1 не открылся, выведем лог Xray
        print(f"   ⚠️ Ошибка прокси: {e}")
        process.terminate()
        log_file.close()
        with open("xray_error.log", "r") as f:
            print(f"   📝 Лог Xray: {f.read().strip()}")
        return results

    process.terminate()
    log_file.close()
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
            if "security=reality" in line:
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
    tiktok_links, google_ai_links, working_links = [], [], []

    print(f"🔍 Начинаем проверку {len(unique_links)} серверов...")
    
    for link in unique_links:
        name = unquote(urlparse(line).fragment if '#' in line else "NoName")
        print(f"🧪 Тестируем: {name[:40]}...")
        res = test_connectivity(link)
        
        if res["tiktok"] or res["google_ai"]:
            working_links.append(link)
            if res["tiktok"]: tiktok_links.append(link)
            if res["google_ai"]: google_ai_links.append(link)
            print(f"   ✅ OK!")
        else:
            print(f"   ❌ Не прошел")

    if not working_links:
        print("⚠️ Ни один сервер не прошел проверку.")
        return

    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
    data = {"config": "\n".join(working_links), "config_tiktok": "\n".join(tiktok_links), "config_google_ai": "\n".join(google_ai_links)}

    for path, content in data.items():
        try:
            curr = repo.get_contents(path)
            repo.update_file(path, f"Update {path}", content, curr.sha)
        except:
            repo.create_file(path, f"Create {path}", content)

if __name__ == "__main__":
    update_github()
