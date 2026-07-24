# osj_bot/git/file_manager.py
import os
import sys
import re
import json
import subprocess
import time
from datetime import datetime
import textwrap

MAP_FILE = "osj_bot/git/file_map.json"

def fetch_file(source_path: str, retries: int = 3, delay: int = 3) -> str:
    """Fetch file from local path or external URL using curl/wget with retries."""
    attempt = 0
    while attempt < retries:
        try:
            if source_path.startswith(("http://", "https://")):
                # Try curl first
                try:
                    result = subprocess.run(
                        ["curl", "-sL", source_path],
                        capture_output=True, text=True, check=True
                    )
                    return result.stdout
                except Exception:
                    # Fallback to wget
                    result = subprocess.run(
                        ["wget", "-qO-", source_path],
                        capture_output=True, text=True, check=True
                    )
                    return result.stdout
            else:
                with open(source_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"Fetch attempt {attempt+1} failed: {e}")
            attempt += 1
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch file {source_path} after {retries} attempts")

def save_file(content: str, dest_path: str) -> None:
    """Save content to destination path with OSJ Bot timestamp comment (no email)."""
    dir_name = os.path.dirname(dest_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    auto_comment = f"\n\nAuto updated by OSJ Bot {timestamp}\n"
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content + auto_comment)

def md_to_txt(content: str) -> str:
    """Convert Markdown to plain text in license style formatting with 80-char wrapping."""
    # Remove Markdown headers, emphasis, blockquotes, code fences
    text = re.sub(r'[#*_>`]', '', content)
    # Replace links with just the text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Normalize whitespace
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    # Wrap text to 80 characters per line
    wrapped_lines = []
    for paragraph in text.split("\n\n"):
        wrapped = textwrap.fill(paragraph, width=80)
        wrapped_lines.append(wrapped)
    return "\n\n".join(wrapped_lines)

def txt_to_md(content: str) -> str:
    """Convert plain text back to Markdown (simple wrapping)."""
    return f"```\n{content}\n```"

def load_map() -> dict:
    """Load JSON mapping of source to destination files, auto-create if missing."""
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_map(mapping: dict) -> None:
    """Save JSON mapping back to file (create if missing, update if exists)."""
    dir_name = os.path.dirname(MAP_FILE)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

def convert_file(source_path: str, dest_path: str, source_ext: str, dest_ext: str) -> None:
    """Main conversion logic with JSON tracking and audit trail."""
    try:
        mapping = load_map()
        prev_content = None

        if source_path in mapping:
            try:
                with open(mapping[source_path]["dest"], "r", encoding="utf-8") as f:
                    prev_content = f.read()
            except FileNotFoundError:
                prev_content = None

        content = fetch_file(source_path)

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

        # Update mapping with audit info (no email stored)
        mapping[source_path] = {
            "dest": dest_path,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        save_map(mapping)

    except Exception as e:
        print(f"Error during conversion: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python osj_bot/git/file_manager.py <source_path> <dest_path> <source_ext> <dest_ext>")
        sys.exit(1)

    source_path, dest_path, source_ext, dest_ext = sys.argv[1:]
    convert_file(source_path, dest_path, source_ext, dest_ext)
