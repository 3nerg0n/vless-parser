import os
import requests
import base64
import json
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

# Имя файла "Умного сервера"
SMART_CONFIG_FILE = "smart_super_server.json"
MAX_WORKERS = 100

def is_tcp_reachable(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def parse_vless_to_dict(link):
    """Превращает VLESS ссылку в словарь для JSON конфига"""
    try:
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        if params.get('security', [''])[0].lower() != 'reality': return None
        
        host = parsed.hostname
        port = int(parsed.port) if parsed.port else 443
        
        if not is_tcp_reachable(host, port): return None

        return {
            "type": "vless",
            "tag": unquote(parsed.fragment) or host,
            "server": host,
            "server_port": port,
            "uuid": parsed.username,
            "packet_encoding": "xudp",
            "tls": {
                "enabled": True,
                "server_name": params.get('sni', [''])[0],
                "utls": {"enabled": True, "fingerprint": params.get('fp', ['chrome'])[0]},
                "reality": {
                    "enabled": True,
                    "public_key": params.get('pbk', [''])[0],
                    "short_id": params.get('sid', [''])[0]
                }
            }
        }
    except: return None

def generate_singbox_json(nodes):
    """Создает структуру Sing-box с авто-балансировкой"""
    # Разделяем узлы по категориям для внутренней логики
    media_nodes = [n["tag"] for n in nodes if any(x in n["tag"].lower() for x in ["de", "nl", "fi", "ru"])]
    ai_nodes = [n["tag"] for n in nodes if any(x in n["tag"].lower() for x in ["us", "sg", "nl", "uk"])]
    all_tags = [n["tag"] for n in nodes]

    config = {
        "outbounds": [
            # 1. Главный "Супер-выход" (авто-выбор самого быстрого)
            {
                "type": "urltest",
                "tag": "🚀 SUPER-SERVER-AUTO",
                "outbounds": all_tags[:30], # Берем первые 30 живых
                "interval": "1m"
            },
            # 2. Специальный выход для ИИ
            {
                "type": "urltest",
                "tag": "🤖 AI-SMART-PATH",
                "outbounds": ai_nodes[:15] if ai_nodes else all_tags[:15],
                "interval": "5m"
            }
        ] + nodes, # Добавляем сами узлы
        "route": {
            "rules": [
                {"domain_suffix": ["openai.com", "anthropic.com", "chatgpt.com"], "outbound": "🤖 AI-SMART-PATH"},
                {"domain_suffix": ["youtube.com", "googlevideo.com", "ytimg.com"], "outbound": "🚀 SUPER-SERVER-AUTO"},
                {"protocol": "dns", "outbound": "🚀 SUPER-SERVER-AUTO"}
            ],
            "final": "🚀 SUPER-SERVER-AUTO"
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
    print(f"Найдено {len(unique_raw)} ссылок. Создаю Супер-Сервер...")

    valid_nodes = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(parse_vless_to_dict, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res: valid_nodes.append(res)

    if valid_nodes:
        smart_config = generate_singbox_json(valid_nodes)
        with open(SMART_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(smart_config)
        
        # Git Push
        try:
            subprocess.run('git config --global user.name "github-actions[bot]"', shell=True)
            subprocess.run('git config --global user.email "github-actions[bot]@users.noreply.github.com"', shell=True)
            subprocess.run(f'git add {SMART_CONFIG_FILE}', shell=True)
            subprocess.run('git commit -m "Update Smart Super Server"', shell=True)
            subprocess.run('git push', shell=True)
            print("✅ Супер-Сервер обновлен!")
        except: pass

if __name__ == "__main__":
    main()
