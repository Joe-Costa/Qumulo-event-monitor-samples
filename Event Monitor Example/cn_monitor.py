#!/usr/bin/env python3
import urllib3
import configparser
import asyncio
import aiohttp
import json
import os
import yaml
import json
from aiohttp import web


# ─── Configuration ─────────────────────────────────────────────────────────────

config = configparser.ConfigParser()
config.read("cn_monitor.conf")

CLUSTER_ADDRESS   = config["CLUSTER"]["CLUSTER_ADDRESS"]
TOKEN             = config["CLUSTER"]["TOKEN"]
USE_SSL           = config["CLUSTER"].getboolean("USE_SSL")

with open("watched_items.yml", "r") as f:
    watched = yaml.safe_load(f)
WATCHED_PATHS = [p.rstrip("/") for p in watched.get("PATHS", [])]
WATCHED_EXTENSIONS = watched.get("EXTENSIONS", [])
WATCHED_EVENTS    = watched.get("EVENTS", [])
if not WATCHED_EVENTS:
    raise RuntimeError("You must define at least one ACTIONS entry in watched_items.yml")

HEADERS      = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept":        "application/json",
    "Content-Type":  "application/json",
}
REF_PATH     = "%2F/notify?recursive=true"
API_ENDPOINT = f"https://{CLUSTER_ADDRESS}/api/v1/files/{REF_PATH}"


# ─── Tail function to read the contents of a file ────────────────────────────────────

TAIL_LINES = 10

def tail_text(text: str, num_lines: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-num_lines:] if len(lines) > num_lines else lines)

# ─── File content reader ───────────────────────────────────────────────────────

async def fetch_file_via_api(file_id: str, max_bytes: int = 20_000) -> str:
    url = f"https://{CLUSTER_ADDRESS}/api/v1/files/{file_id}/data"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS, ssl=USE_SSL) as resp:
            if resp.status == 200:
                chunk = await resp.content.read(max_bytes)
                return chunk.decode("utf-8", errors="ignore")
            return f"(error {resp.status} fetching data)"


# ─── Event handler ────────────────────────────────────────────────────────────

async def handle_event(event_data: str):
    try:
        changes = json.loads(event_data)
        for fs_event in changes:
            # Trigger only on events we care about
            if fs_event.get("type") not in WATCHED_EVENTS:
                continue

            full_path = "/" + fs_event["path"]
            ext       = os.path.splitext(fs_event["path"])[1].lower()
            directory = os.path.dirname(full_path)
            
            # Sample trigger if a match or extension + watched directory is found
            if ext in WATCHED_EXTENSIONS and any(directory.startswith(p) for p in WATCHED_PATHS):
                basename = os.path.basename(full_path)
                file_id  = fs_event["spine"][-1]

                # Sample trigger if a new file is created or appended to
                if fs_event.get("type") in ["child_file_added","child_data_written"]:
                    full_text = await fetch_file_via_api(file_id)
                    snippet   = tail_text(full_text, TAIL_LINES)
                    
                    # Do some pretty printing of the text contents
                    lines   = snippet.splitlines()
                    max_len = max(len(line) for line in lines)
                    separator = "-" * max_len

                    # Body of the output message
                    msg = (
                        f"📄 *New file* `{basename}` in `{directory}`\n\n"
                        f"{separator}\n"
                        f"{snippet}\n"
                        f"{separator}"
)
                    # All we do with this info is print it out to stdout.  You could trigger some other function 
                    # with the contents of msg
                    print(msg)

            # Sample trigger if new directory is created in our watched directories
            elif fs_event.get("type") in ["child_dir_added"] and any(directory.startswith(p) for p in WATCHED_PATHS):
                basename = os.path.basename(full_path)

                # Body of the output message
                msg = (
                    f"📂 *New directory created* `{basename}` in `{directory}`\n"                   
                )
                # All we do with this info is print it out to stdout.  
                # You could trigger some other function with the contents of msg
                print(msg)

    # Handle occasional returned event weirdness
    except json.JSONDecodeError:
        print(f"Non‑JSON event received: {event_data}")


# ─── SSE monitor ──────────────────────────────────────────────────────────────

async def monitor_api():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_ENDPOINT, headers=HEADERS, ssl=USE_SSL) as resp:
            try:
                while True:
                    line = await resp.content.readline()
                    if not line:
                        break
                    data = line.decode().strip()
                    if data.startswith("data:"):
                        await handle_event(data.removeprefix("data:").strip())
            except asyncio.CancelledError:
                print("Monitoring canceled. Cleaning up...")
                raise  # ← re‑raise so main() sees the cancellation


# ─── Main func ──────────────────────────────────────────────────────────────

async def main():
    while True:
        try:
            await monitor_api()
        except (asyncio.CancelledError, KeyboardInterrupt):
            print("Quitting…")
            break
        except Exception as e:
            print(f"Error in monitor_api: {e}. Reconnecting in 5s…")
            await asyncio.sleep(5)

if __name__ == "__main__":
    if not USE_SSL:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    asyncio.run(main())

