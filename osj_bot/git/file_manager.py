# osj_bot/git/file_manager.py
import os
import sys
import requests
import re
import json
from datetime import datetime

MAP_FILE = "osj_bot/git/file_map.json"

def fetch_file(source_path: str) -> str:
    """Fetch file from local path or URL."""
    if source_path.startswith(("http://", "https://")):
        response = requests.get(source_path)
        response.raise_for_status()
        return response.text
    else:
        with open(source_path, "r", encoding="utf-8") as f:
            return f.read()

def save_file(content: str, dest_path: str) -> None:
    """Save content to destination path with OSJ Bot timestamp comment."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    auto_comment = f"\n\n<!-- Auto updated by OSJ Bot {timestamp} -->\n"
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content + auto_comment)

def md_to_txt(content: str) -> str:
    """Convert Markdown to plain text (basic stripping)."""
    text = re.sub(r'[#*_>`]', '', content)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # links
    return text.strip()

def txt_to_md(content: str) -> str:
    """Convert plain text to Markdown (simple wrapping)."""
    return f"```\n{content}\n```"

def load_map() -> dict:
    """Load JSON mapping of source to destination files."""
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_map(mapping: dict) -> None:
    """Save JSON mapping back to file."""
    os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

def convert_file(source_path: str, dest_path: str, source_ext: str, dest_ext: str) -> None:
    """Main conversion logic with JSON tracking."""
    mapping = load_map()
    prev_content = None

    if source_path in mapping:
        try:
            with open(mapping[source_path], "r", encoding="utf-8") as f:
                prev_content = f.read()
        except FileNotFoundError:
            prev_content = None

    content = fetch_file(source_path)

    # Only convert if content changed
    if prev_content == content:
        print(f"No changes detected in {source_path}, skipping conversion.")
        return

    if source_ext == dest_ext:
        save_file(content, dest_path)
    elif source_ext == "md" and dest_ext == "txt":
        converted = md_to_txt(content)
        save_file(converted, dest_path)
    elif source_ext == "txt" and dest_ext == "md":
        converted = txt_to_md(content)
        save_file(converted, dest_path)
    else:
        raise ValueError(f"Unsupported conversion: {source_ext} -> {dest_ext}")

    # Update mapping
    mapping[source_path] = dest_path
    save_map(mapping)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python osj_bot/git/file_manager.py <source_path> <dest_path> <source_ext> <dest_ext>")
        sys.exit(1)

    source_path, dest_path, source_ext, dest_ext = sys.argv[1:]
    convert_file(source_path, dest_path, source_ext, dest_ext)
