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
OSJ_CENTER_WIDTH = 80  # only used to center title/preamble header lines


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


def osj_md_to_license_txt(content, center_width=OSJ_CENTER_WIDTH):
    """
    Convert Markdown license text into plain-text formatting similar to
    MIT/Apache-style LICENSE files.

    - No hard line-wrapping/capping: paragraphs and list items are emitted
      as full single lines, whatever their length.
    - Lines before the PREAMBLE section are centered (title/header block).
    - Lists keep their bullet/number markers instead of losing them to
      plain text extraction.
    - Blocks are separated by blank lines by walking top-level HTML
      elements rather than flattening everything with get_text().
    """
    html = markdown.markdown(content, extensions=["extra"])
    soup = BeautifulSoup(html, "html.parser")

    blocks = []
    preamble_found = False

    for el in soup.find_all(recursive=False):
        tag = el.name

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = el.get_text(" ", strip=True)
            if "PREAMBLE" in text.upper():
                preamble_found = True
            if not preamble_found:
                blocks.append(text.center(center_width))
            else:
                blocks.append(text)

        elif tag == "p":
            text = el.get_text(" ", strip=True)
            if "PREAMBLE" in text.upper():
                preamble_found = True
            if not preamble_found:
                blocks.append(text.center(center_width))
            else:
                blocks.append(text)

        elif tag in ("ul", "ol"):
            items = []
            for i, li in enumerate(el.find_all("li", recursive=False), start=1):
                li_text = li.get_text(" ", strip=True)
                marker = f"{i}." if tag == "ol" else "-"
                items.append(f"{marker} {li_text}")
            blocks.append("\n".join(items))

        elif tag == "hr":
            blocks.append("-" * center_width)

        else:
            text = el.get_text(" ", strip=True)
            if text:
                blocks.append(text)

    return "\n\n".join(b for b in blocks if b.strip() != "" or b == "")


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

        # NOTE: previously this compared the freshly-fetched raw Markdown
        # against the *converted* plain-text file read back from dest_path.
        # Those are never equal (one is Markdown, the other is centered/
        # converted output), so the "skip if unchanged" check never fired.
        # Fix: cache the raw source content itself in file_map.json and
        # compare against that instead.
        prev_raw_content = mapping.get(source_path, {}).get("raw_content")

        content = osj_fetch_file(source_path)

        if prev_raw_content == content:
            print(f"No changes detected in {source_path}, skipping conversion.")
            return

        converted = osj_md_to_license_txt(content)
        osj_save_license(converted, dest_path)

        mapping[source_path] = {
            "dest": dest_path,
            "raw_content": content,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
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
