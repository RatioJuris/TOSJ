import os
import sys
import json
import subprocess
import time
from datetime import datetime
import markdown
from bs4 import BeautifulSoup

def osj_ensure_dependencies():
    try:
        import markdown
        import bs4
    except ImportError:
        print("Warning: Required libraries missing. Installing markdown and beautifulsoup4...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown", "beautifulsoup4"])
    finally:
        global markdown, BeautifulSoup
        import markdown
        from bs4 import BeautifulSoup

osj_ensure_dependencies()

OSJ_MAP_FILE = "osj_bot/git/file_map.json"

def osj_fetch_file(source_path, retries=3, delay=3):
    attempt = 0
    while attempt < retries:
        try:
            if source_path.startswith(("http://", "https://")):
                try:
                    result = subprocess.run(["curl", "-sL", source_path], capture_output=True, text=True, check=True)
                    return result.stdout
                except Exception:
                    result = subprocess.run(["wget", "-qO-", source_path], capture_output=True, text=True, check=True)
                    return result.stdout
            else:
                with open(source_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"Fetch attempt {attempt+1} failed: {e}")
            attempt += 1
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch file {source_path} after {retries} attempts")

def osj_save_license(content, dest_path):
    dir_name = os.path.dirname(dest_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    footer = (
        f"\n\n<!-- Update Note: Auto updated and maintained by OSJ Bot. Do not change this file.\n"
        f'{{"bot":"OSJ Bot","timestamp":"{timestamp}","license":"The Open Source Journal"}}\n'
        f"-->\n"
    )
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content + footer)

def osj_md_to_license_txt(content):
    html = markdown.markdown(content)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n").strip()
    lines = text.split("\n")
    converted_lines = []
    preamble_found = False
    for line in lines:
        if "PREAMBLE" in line:
            preamble_found = True
            converted_lines.append(line)
        elif not preamble_found:
            converted_lines.append(line.center(80))
        else:
            converted_lines.append(line)
    return "\n".join(converted_lines)

def osj_load_map():
    if os.path.exists(OSJ_MAP_FILE):
        try:
            with open(OSJ_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def osj_save_map(mapping):
    dir_name = os.path.dirname(OSJ_MAP_FILE)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(OSJ_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

def osj_convert_license(source_path, dest_path):
    try:
        mapping = osj_load_map()
        prev_content = None
        if source_path in mapping:
            try:
                with open(mapping[source_path]["dest"], "r", encoding="utf-8") as f:
                    prev_content = f.read()
            except FileNotFoundError:
                prev_content = None
        content = osj_fetch_file(source_path)
        if prev_content == content:
            print(f"No changes detected in {source_path}, skipping conversion.")
            return
        converted = osj_md_to_license_txt(content)
        osj_save_license(converted, dest_path)
        mapping[source_path] = {
            "dest": dest_path,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        osj_save_map(mapping)
    except Exception as e:
        print(f"Error during conversion: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python osj_bot/git/file_manager.py <source_license_md> <dest_license_txt>")
        sys.exit(1)
    source_path, dest_path = sys.argv[1:]
    osj_convert_license(source_path, dest_path)
