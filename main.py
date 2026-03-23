import os
import requests
import base64
import json
import time
import subprocess
import socket
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# Имя итогового файла
SMART_CONFIG_FILE = "smart_super_server.json"
MAX_WORKERS = 100 

def is_tcp_reachable(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def vless_to_outbound(link):
    """Преобразует VLESS ссылку в формат Sing-box outbound"""
    try:
        p = urlparse(link)
        qs = parse_qs(p.query)
        
        # Проверяем только Reality
        if qs.get('security', [''])[0].lower() != 'reality':
            return None

        host = p.hostname
        port = int(p.port) if p.port else 443
        
        if not is_tcp_reachable(host, port):
            return None

        tag = unquote(p.fragment) or host
        
        return {
            "type": "vless",
            "tag": tag,
            "server": host,
            "server_port": port,
            "uuid": p.username,
            "packet_encoding": "xudp",
            "tls": {
                "enabled": True,
                "server_name": qs.get('sni', [''])[0],
                "utls": {"enabled": True, "fingerprint": qs.get('fp', ['chrome'])[0]},
                "reality": {
                    "enabled": True,
                    "public_key": qs.get('pbk', [''])[0],
                    "short_id": qs.get('sid', [''])[0]
                }
            }
        }
    except:
        return None

def generate_smart_json(outbounds):
    """Создает структуру Sing-box с балансировкой и правилами"""
    tags = [o["tag"] for o in outbounds]
    
    # Группируем теги по странам для правил
    media_tags = [t for t in tags if any(x in t.lower() for x in ["de", "nl", "fi", "ru", "germany", "netherlands"])]
    ai_tags = [t for t in tags if any(x in t.lower() for x in ["us", "sg", "nl", "usa", "singapore"])]

    config = {
        "outbounds": [
            # 1. Авто-выбор (основной балансировщик)
            {
                "type": "urltest",
                "tag": "🚀 AUTO-SELECT (FASTEST)",
                "outbounds": tags[:50], # Берем топ-50 живых
                "interval": "1m",
                "idle_timeout": "30m"
            },
            # 2. Группа для ИИ
            {
                "type": "urltest",
                "tag": "🤖 AI-UNBLOCK-PATH",
                "outbounds": ai_tags[:20] if ai_tags else tags[:20],
                "interval": "5m"
            }
        ] + outbounds,
        "route": {
            "rules": [
                # Правила для нейросетей
                {
                    "domain_suffix": ["openai.com", "chatgpt.com", "anthropic.com", "claude.ai", "bing.com"],
                    "outbound": "🤖 AI-UNBLOCK-PATH"
                },
                # Правила для YouTube и Telegram
                {
                    "domain_suffix": ["youtube.com", "googlevideo.com", "ytimg.com", "t.me", "telegram.org"],
                    "outbound": "🚀 AUTO-SELECT (FASTEST)"
                }
            ],
            "final": "🚀 AUTO-SELECT (FASTEST)",
            "auto_detect_interface": True
        }
    }
    return json.dumps(config, indent=2, ensure_ascii=False)

def main():
    raw_links = []
    for url in SOURCE_URLS:
        try:
            res = requests.get(url, timeout=15)
            data = res.text
            if "vless://" not in data:
                try: data = base64.b64decode(data).decode('utf-8')
                except: pass
            for line in data.splitlines():
                if line.strip().startswith("vless://"):
                    raw_links.append(line.strip())
        except: continue

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} ссылок. Начинаю проверку и сборку умного конфига...")

    valid_outbounds = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(vless_to_outbound, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res:
                valid_outbounds.append(res)

    if not valid_outbounds:
        print("Нет рабочих серверов.")
        return

    # Генерируем JSON
    smart_json = generate_smart_json(valid_outbounds)
    
    with open(SMART_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(smart_json)

    # Отправка в репозиторий
    try:
        subprocess.run('git config --global user.name "github-actions[bot]"', shell=True)
        subprocess.run('git config --global user.email "github-actions[bot]@users.noreply.github.com"', shell=True)
        subprocess.run(f'git add {SMART_CONFIG_FILE}', shell=True)
        subprocess.run('git commit -m "Update Smart Super Config"', shell=True)
        subprocess.run('git push', shell=True)
        print(f"✅ Умный конфиг успешно обновлен! Найдено {len(valid_outbounds)} узлов.")
    except Exception as e:
        print(f"Ошибка Git: {e}")

if __name__ == "__main__":
    main()
