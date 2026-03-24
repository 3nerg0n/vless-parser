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

CONFIG_FILENAME = "auto_balancer.json"
MAX_WORKERS = 100 

def is_tcp_reachable(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def vless_to_outbound(link):
    try:
        p = urlparse(link)
        qs = parse_qs(p.query)
        if qs.get('security', [''])[0].lower() != 'reality': return None
        host, port = p.hostname, int(p.port) if p.port else 443
        if not is_tcp_reachable(host, port): return None
        
        return {
            "type": "vless",
            "tag": unquote(p.fragment) or host,
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
    except: return None

def generate_full_config(nodes):
    tags = [n["tag"] for n in nodes]
    
    config = {
        "log": {"level": "info"},
        "dns": {
            "servers": [
                {"tag": "dns-remote", "address": "https://1.1.1.1/dns-query", "detour": "🚀 AUTO-SELECT"},
                {"tag": "dns-direct", "address": "8.8.8.8", "detour": "direct"}
            ],
            "rules": [
                {"outbound": "any", "server": "dns-remote"}
            ],
            "strategy": "prefer_ipv4"
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "🚀 СУПЕР-СЕРВЕР",
                "listen": "127.0.0.1",
                "listen_port": 2080,
                "sniff": True
            }
        ],
        "outbounds": [
            {
                "type": "urltest",
                "tag": "🚀 AUTO-SELECT",
                "outbounds": tags[:50],
                "url": "https://www.gstatic.com/generate_204",
                "interval": "1m"
            },
            {
                "type": "selector",
                "tag": "Manual-Select (Выбрать вручную)",
                "outbounds": ["🚀 AUTO-SELECT"] + tags
            },
            {"type": "direct", "tag": "direct"},
            {"type": "dns", "tag": "dns-out"}
        ] + nodes,
        "route": {
            "rules": [
                {"protocol": "dns", "outbound": "dns-out"},
                {"network": "udp", "port": 443, "outbound": "direct"}, # Пропуск QUIC для YouTube (иногда помогает)
                {"domain_suffix": ["youtube.com", "googlevideo.com", "openai.com", "t.me"], "outbound": "🚀 AUTO-SELECT"}
            ],
            "final": "🚀 AUTO-SELECT",
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
                if line.strip().startswith("vless://"): raw_links.append(line.strip())
        except: continue

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} ссылок. Проверка...")

    valid_nodes = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(vless_to_outbound, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res: valid_nodes.append(res)

    if valid_nodes:
        full_json = generate_full_config(valid_nodes)
        with open(CONFIG_FILENAME, "w", encoding="utf-8") as f:
            f.write(full_json)
        
        try:
            subprocess.run('git config --global user.name "github-actions[bot]"', shell=True)
            subprocess.run('git config --global user.email "github-actions[bot]@users.noreply.github.com"', shell=True)
            subprocess.run(f'git add {CONFIG_FILENAME}', shell=True)
            subprocess.run('git commit -m "Fix Streisand Config"', shell=True)
            subprocess.run('git push', shell=True)
            print("✅ Конфиг обновлен!")
        except: pass

if __name__ == "__main__":
    main()
