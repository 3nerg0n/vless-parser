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

        # Формируем конфиг с учетом Flow и Fingerprint
        config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": 10808, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": address, "port": port,
                        "users": [{
                            "id": uuid, 
                            "encryption": "none",
                            "flow": params.get('flow', '') # Добавили FLOW (важно для Vision)
                        }]
                    }]
                },
                "streamSettings": {
                    "network": params.get('type', 'tcp'),
                    "security": params.get('security', 'none'),
                    "realitySettings": {
                        "show": False,
                        "fingerprint": params.get('fp', 'chrome'), # Добавили Fingerprint
                        "serverName": params.get('sni', ''),
                        "publicKey": params.get('pbk', ''),
                        "shortId": params.get('sid', ''),
                        "spiderX": params.get('spx', '')
                    }
                }
            }]
        }
        with open('test_config.json', 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"❌ Ошибка парсинга ссылки: {e}")
        return False

def test_connectivity(vless_link):
    results = {"tiktok": False, "google_ai": False}
    if not create_xray_config(vless_link):
        return results

    # Запускаем Xray
    process = subprocess.Popen(["./xray", "-c", "test_config.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5) # Увеличили ожидание до 5 секунд для стабильности

    proxies = {"http": "socks5h://127.0.0.1:10808", "https": "socks5h://127.0.0.1:10808"}
    
    # Тест 1: TikTok
    try:
        r = requests.get("https://www.tiktok.com", proxies=proxies, timeout=15)
        if r.status_code == 200: results["tiktok"] = True
    except Exception as e:
        pass # Просто не доступен

    # Тест 2: Google AI
    try:
        r = requests.get("https://aistudio.google.com", proxies=proxies, timeout=15)
        if r.status_code == 200: results["google_ai"] = True
    except Exception as e:
        pass

    process.terminate()
    process.wait()
    return results

def parse_vless_links(raw_data):
    try:
        decoded_data = base64.b64decode(raw_data.strip()).decode('utf-8')
    except:
        decoded_data = raw_data
    
    lines = decoded_data.splitlines()
    filtered = []
    keywords = ["germany", "netherlands"]
    
    for line in lines:
        line = line.strip()
        if line.startswith("vless://"):
            # Проверяем, что это именно REALITY и TCP (как ты просил в начале)
            if "security=reality" in line and "type=tcp" in line:
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
        name = unquote(urlparse(link).fragment)
        print(f"🧪 Тестируем: {name[:50]}...") # Обрезаем длинные имена в логах
        res = test_connectivity(link)
        
        if res["tiktok"] or res["google_ai"]:
            working_links.append(link)
            status = []
            if res["tiktok"]: 
                tiktok_links.append(link)
                status.append("TikTok")
            if res["google_ai"]: 
                google_ai_links.append(link)
                status.append("GoogleAI")
            print(f"   ✅ РАБОТАЕТ: {', '.join(status)}")
        else:
            print(f"   ❌ Не прошел тесты")

    if not working_links:
        print("⚠️ Ни один сервер не прошел проверку. Файлы не обновлены.")
        return

    # Сохранение на GitHub
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
