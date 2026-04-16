import json
import os
import subprocess
import re
import requests
import time

RPC_REGEX = r"\[BloxstrapRPC.*?\}\}\}"
CACHE_PATH = "./thumbnailCache.json"
thumbnail_cache = {}

if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r") as f:
        thumbnail_cache = json.load(f)

def push_biome_status(biome):
    subprocess.run(f'termux-notification --priority min --id "st_notifier" --title "Current Biome: {biome}"', shell=True)

def send_webhook(config, biome, is_rare, asset_id="", title="Biome Started"):
    url = config["webhook"]["url"]
    if not url: return

    # Xử lý thumbnail
    if asset_id and asset_id not in thumbnail_cache:
        res = requests.get(f"https://thumbnails.roblox.com/v1/assets?assetIds={asset_id}&size=512x512&format=Png&isCircular=false")
        if res.status_code == 200:
            data = res.json()
            if data['data']:
                thumbnail_cache[asset_id] = data['data'][0]['imageUrl']
                with open(CACHE_PATH, "w") as f: json.dump(thumbnail_cache, f)

    body = {
        "content": "@everyone" if is_rare else "",
        "embeds": [{
            "author": {"name": title},
            "title": biome,
            "description": f"**Started at:** <t:{int(time.time())}:R>",
        }]
    }

    if config.get("private_server_link"):
        body["components"] = [{
            "type": 1,
            "components": [{
                "type": 2, "style": 5, "label": "Join Server", "url": config["private_server_link"]
            }]
        }]

    if asset_id in thumbnail_cache:
        body["embeds"][0]["thumbnail"] = {"url": thumbnail_cache[asset_id]}

    try:
        requests.post(f"{url}?with_components=true", json=body)
    except Exception as e:
        print(f"Failed to send webhook: {e}")

def start_notifier(config):
    active_biomes = [b for b, enabled in config["webhook_notification"].items() if enabled]
    
    send_webhook(config, "Biome Notifier started!", False, "", "Status")
    if config["push_current_biome_notification"]:
        push_biome_status("UNKNOWN")

    # Xóa log cũ và bắt đầu đọc logcat
    subprocess.run(["rish", "-c", "logcat -c"])
    process = subprocess.Popen(["rish", "-c", "logcat"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    prev_state = ""

    for line in iter(process.stdout.readline, ""):
        match = re.search(RPC_REGEX, line)
        if match:
            try:
                # Cắt bỏ phần "[BloxstrapRPC" để lấy JSON
                json_str = match.group(0)[15:] 
                rpc_data = json.loads(json_str)["data"]

                small_image = rpc_data.get("smallImage", {})
                large_image = rpc_data.get("largeImage", {})

                if small_image.get("hoverText") == "Sol's RNG" and large_image:
                    biome = large_image.get("hoverText")
                    state = rpc_data.get("state")
                    asset_id = large_image.get("assetId")

                    if state == prev_state or not prev_state:
                        if biome in active_biomes:
                            is_rare = biome in ["GLITCHED", "DREAMSPACE", "CYBERSPACE"]
                            if is_rare:
                                if config["rare_biome_actions"]["toast"]:
                                    subprocess.run(f'termux-toast "{biome} just started!!!"', shell=True)
                                if config["rare_biome_actions"]["vibrate"]:
                                    subprocess.run("termux-vibrate", shell=True)
                            
                            if config["webhook"]["enable"]:
                                send_webhook(config, biome, is_rare, asset_id)

                        if config["push_current_biome_notification"]:
                            push_biome_status(biome)
                    
                    prev_state = state
            except Exception as e:
                print(f"Error parsing RPC: {e}")
