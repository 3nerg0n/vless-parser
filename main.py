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

# Имя итогового файла, который вы вставите в приложение
SMART_CONFIG_FILE = "smart_super_server.json"
MAX_WORKERS = 100  # Скорость проверки (потоки)

def is_tcp_reachable(host, port, timeout=1.5):
    """Проверяет, жив ли сервер"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def vless_to_outbound(link):
    """Преобразует VLESS Reality ссылку в объект Sing-box"""
    try:
        p = urlparse(link)
        qs = parse_qs(p.query)
        
        # Работаем только с Reality (самый надежный протокол)
        if qs.get('security', [''])[0].lower() != 'reality':
            return None

        host = p.hostname
        port = int(p.port) if p.port else 443
        
        # Проверка доступности порта
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
    """Создает ПОЛНЫЙ Sing-box конфиг с DNS и маршрутами"""
    tags = [o["tag"] for o in outbounds]
    
    # Фильтруем теги для спец-групп
    media_tags = [t for t in tags if any(x in t.lower() for x in ["de", "nl", "fi", "ru", "germany"])]
    ai_tags = [t for t in tags if any(x in t.lower() for x in ["us", "sg", "nl", "usa", "singapore"])]

    config = {
        "log": {"level": "info"},
        "dns": {
            "servers": [
                {"tag": "dns-remote", "address": "https://8.8.8.8/dns-query", "detour": "🚀 AUTO-SELECT"},
                {"tag": "dns-direct", "address": "8.8.8.8", "detour": "direct"}
            ],
            "rules": [
                {"outbound": "any", "server": "dns-remote"},
                {"domain": ["openai.com", "chatgpt.com", "anthropic.com", "claude.ai"], "server": "dns-remote"}
            ],
            "strategy": "prefer_ipv4"
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 2080,
                "sniff": True
            }
        ],
        "outbounds": [
            # 1. Авто-выбор самого быстрого сервера
            {
                "type": "urltest",
                "tag": "🚀 AUTO-SELECT",
                "outbounds": tags[:60], # Берем топ-60 живых
                "url": "https://www.gstatic.com/generate_204",
                "interval": "1m",
                "tolerance": 50
            },
            # 2. Ручной выбор (если авто-выбор не подходит)
            {
                "type": "selector",
                "tag": "Manual-Select",
                "outbounds": ["🚀 AUTO-SELECT"] + tags
            },
            # 3. Группа для Нейросетей
            {
                "type": "urltest",
                "tag": "🤖 AI-PATH",
                "outbounds": ai_tags[:20] if ai_tags else tags[:20],
                "url": "https://www.gstatic.com/generate_204",
                "interval": "5m"
            },
            {"type": "direct", "tag": "direct"},
            {"type": "dns", "tag": "dns-out"}
        ] + outbounds,
        "route": {
            "rules": [
                {"protocol": "dns", "outbound": "dns-out"},
                # Нейросети
                {"domain_suffix": ["openai.com", "chatgpt.com", "anthropic.com", "claude.ai", "bing.com"], "outbound": "🤖 AI-PATH"},
                # YouTube, Telegram и Google
                {"domain_suffix": ["youtube.com", "googlevideo.com", "ytimg.com", "t.me", "telegram.org", "google.com"], "outbound": "🚀 AUTO-SELECT"},
                # Всё остальное
                {"network": "tcp", "outbound": "🚀 AUTO-SELECT"}
            ],
            "final": "🚀 AUTO-SELECT",
            "auto_detect_interface": True
        }
    }
    return json.dumps(config, indent=2, ensure_ascii=False)

def main():
    raw_links = []
    print("--- Начинаю сбор ссылок ---")
    for url in SOURCE_URLS:
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                data = res.text
                if "vless://" not in data:
                    try: data = base64.b64decode(data).decode('utf-8')
                    except: pass
                for line in data.splitlines():
                    if line.strip().startswith("vless://"):
                        raw_links.append(line.strip())
        except: continue

    unique_raw = list(dict.fromkeys(raw_links))
    print(f"Найдено {len(unique_raw)} уникальных ссылок. Начинаю проверку...")

    valid_outbounds = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(vless_to_outbound, link) for link in unique_raw]
        for future in as_completed(futures):
            res = future.result()
            if res:
                valid_outbounds.append(res)

    if not valid_outbounds:
        print("❌ Рабочих серверов не найдено. Обновление отменено.")
        return

    print(f"✅ Найдено живых серверов: {len(valid_outbounds)}. Генерирую конфиг...")
    
    # Генерируем и сохраняем JSON
    smart_json = generate_smart_json(valid_outbounds)
    with open(SMART_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(smart_json)

    # Отправка в GitHub
    try:
        subprocess.run('git config --global user.name "github-actions[bot]"', shell=True)
        subprocess.run('git config --global user.email "github-actions[bot]@users.noreply.github.com"', shell=True)
        subprocess.run(f'git add {SMART_CONFIG_FILE}', shell=True)
        
        # Проверка, есть ли изменения
        status = subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True).stdout.strip()
        if not status:
            print("Изменений нет. Пропускаю пуш.")
            return

        subprocess.run('git commit -m "Update Smart Super Config: ' + str(len(valid_outbounds)) + ' nodes"', shell=True)
        subprocess.run('git push', shell=True)
        print(f"🚀 Конфиг успешно обновлен и отправлен в репозиторий!")
    except Exception as e:
        print(f"Ошибка Git: {e}")

if __name__ == "__main__":
    main()
