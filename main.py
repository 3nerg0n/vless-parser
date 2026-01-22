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
FILE_PATH_ALL = "config"
FILE_PATH_TIKTOK = "config_tiktok"
FILE_PATH_AI = "config_google_ai"

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
        params = parse_qs(parsed.query)
        user_info = parsed.netloc.split('@')
        uuid = user_info[0]
        host_port = user_info[1].split(':')
        address = host_port[0]
        port = int(host_port[1])

        config = {
            "log": {"loglevel": "none"},
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
    except Exception as e:
        print(f"❌ Ошибка создания конфига Xray: {e}")
        return False

def test_connectivity(vless_link):
    results = {"tiktok": False, "google_ai": False}
    if not create_xray_config(vless_link):
        return results

    # Запускаем Xray
    process = subprocess.Popen(["./xray", "-c", "test_config.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3) # Даем время на запуск и хендшейк

    proxies = {
        "http": "socks5h://127.0.0.1:10808",
        "https": "socks5h://127.0.0.1:10808"
    }
    
    try:
        # Проверка TikTok
        r_tk = requests.get("https://www.tiktok.com", proxies=proxies, timeout=15)
        if r_tk.status_code == 200:
            results["tiktok"] = True
    except Exception as e:
        print(f"   - TikTok недоступен")

    try:
        # Проверка Google AI (Gemini)
        r_ai = requests.get("https://aistudio.google.com", proxies=proxies, timeout=15)
        if r_ai.status_code == 200:
            results["google_ai"] = True
    except Exception as e:
        print(f"   - Google AI недоступен")

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
            name = unquote(urlparse(line).fragment).lower()
            if any(k in name for k in keywords):
                filtered.append(line)
    return list(dict.fromkeys(filtered))

def update_github():
    install_xray()
    all_links = []
    for url in SOURCE_URLS:
        try:
            print(f"🌐 Загрузка из {url}...")
            r = requests.get(url, timeout=20)
            links = parse_vless_links(r.text)
            all_links.extend(links)
            print(f"✅ Найдено {len(links)} потенциальных серверов")
        except Exception as e:
            print(f"❌ Ошибка загрузки {url}: {e}")
    
    unique_links = list(dict.fromkeys(all_links))
    
    tiktok_links = []
    google_ai_links = []
    working_links = []

    print(f"🔍 Начинаем проверку {len(unique_links)} серверов...")
    for link in unique_links:
        name = unquote(urlparse(link).fragment)
        print(f"🧪 Тестируем: {name}")
        res = test_connectivity(link)
        
        # Если сервер прошел хотя бы один тест, добавляем в общий список
        if res["tiktok"] or res["google_ai"]:
            working_links.append(link)
            if res["tiktok"]: 
                print(f"   [+] TikTok OK")
                tiktok_links.append(link)
            if res["google_ai"]: 
                print(f"   [+] Google AI OK")
                google_ai_links.append(link)
        else:
            print(f"   [-] Сервер не прошел тесты")

    # Если вообще ничего не работает, не будем затирать файлы, а просто выйдем
    if not working_links:
        print("⚠️ ВНИМАНИЕ: Ни один сервер не прошел проверку. Файлы не будут обновлены.")
        return

    # Сохранение
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    data_to_save = {
        FILE_PATH_ALL: "\n".join(working_links),
        FILE_PATH_TIKTOK: "\n".join(tiktok_links),
        FILE_PATH_AI: "\n".join(google_ai_links)
    }

    for path, content in data_to_save.items():
        try:
            curr = repo.get_contents(path)
            repo.update_file(path, f"Update {path}", content, curr.sha)
            print(f"💾 Файл {path} обновлен")
        except:
            repo.create_file(path, f"Create {path}", content)
            print(f"🆕 Файл {path} создан")

if __name__ == "__main__":
    update_github()
