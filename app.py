import os
import io
import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from PIL import Image
from collections import defaultdict
from datetime import datetime
from tkinter import Tk, filedialog
import unicodedata
import re

# --- Configuration ---
MAX_SIZE = 400  # Target size for album art (px)
SUPPORTED_EXTENSIONS = ('.mp3',)
ENABLE_LOGGING = True  # Set to False to disable logfile generation

# --- Helper: Normalize names for duplicate detection ---
def normalize_name(name: str):
    """Normalize music filename for duplicate detection."""
    name = os.path.splitext(name)[0]
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = name.lower()
    name = re.sub(r'[^a-z0-9 ]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_audio_duration(path: str):
    """Return duration in seconds."""
    try:
        audio = MP3(path)
        return int(audio.info.length)
    except:
        return None

# --- Function to download album art from iTunes API ---
def download_album_art(artist: str, title: str, size: int = 600):
    """Fetch album art from iTunes API based on artist and title."""
    try:
        query = f"{artist} {title}".replace(' ', '+')
        url = f"https://itunes.apple.com/search?term={query}&limit=1"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['resultCount'] > 0:
            artwork_url = data['results'][0]['artworkUrl100'].replace('100x100', f'{size}x{size}')
            return requests.get(artwork_url, timeout=5).content
    except Exception:
        pass
    return None

# --- Resize image to 400x400 ---
def resize_to_400(image_bytes: bytes) -> bytes:
    """Resize image to 400x400 px with padding if needed."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_SIZE, MAX_SIZE))
        new_img = Image.new("RGB", (MAX_SIZE, MAX_SIZE), (0, 0, 0))
        x = (MAX_SIZE - img.width) // 2
        y = (MAX_SIZE - img.height) // 2
        new_img.paste(img, (x, y))
        output = io.BytesIO()
        new_img.save(output, format='JPEG')
        return output.getvalue()

# --- Extract current embedded art ---
def get_embedded_art(file_path: str):
    """Return the embedded album art as bytes if it exists."""
    audio = MP3(file_path, ID3=ID3)
    for tag in audio.tags.values():
        if isinstance(tag, APIC):
            return tag.data
    return None

# --- Embed album art ---
def embed_album_art(file_path: str, image_bytes: bytes):
    """Embed or replace album art in MP3 file."""
    try:
        audio = MP3(file_path, ID3=ID3)
        try:
            audio.add_tags()
        except error:
            pass

        audio.tags.delall("APIC")
        resized = resize_to_400(image_bytes)
        audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=resized))
        audio.save()
    except Exception as e:
        print(f"⚠️ Failed to embed art for {os.path.basename(file_path)}: {e}")

# --- Extract artist and title from filename ---
def extract_metadata_from_filename(filename: str):
    """Extract artist and title from filename pattern 'Artist - Title.mp3'."""
    name = os.path.splitext(os.path.basename(filename))[0]
    if ' - ' in name:
        artist, title = name.split(' - ', 1)
        return artist.strip(), title.strip()
    return None, None

# --- Get image size ---
def get_image_size(image_bytes: bytes):
    """Return (width, height) of an image."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return img.width, img.height
    except Exception:
        return None, None

# --- Save log ---
def save_log(folder_path: str, log_lines: list[str]):
    if not ENABLE_LOGGING:
        return
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"log_{timestamp}.txt"
        log_path = os.path.join(script_dir, log_filename)

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("--- Album Art Script Log ---\n")
            f.write("Run at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
            for line in log_lines:
                f.write(line + "\n")

        print(f"📝 Log saved: {log_path}")
    except Exception as e:
        print(f"⚠️ Failed to save log: {e}")

# --- Main processing ---
def process_folder(folder_path: str):
    stats = defaultdict(int)
    log_lines = []
    seen = {}
    duplicates = []

    print("\n🔍 Scanning folder...\n")

    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.lower().endswith(SUPPORTED_EXTENSIONS):
                continue

            full_path = os.path.join(root, file)
            stats["total_checked"] += 1

            # --- Duplicate detection ---
            norm = normalize_name(file)
            dur = get_audio_duration(full_path)

            if dur is not None:
                if norm in seen:
                    for prev in seen[norm]:
                        if abs(prev["duration"] - dur) <= 2:
                            duplicates.append((prev["path"], full_path))
                            break
                    seen[norm].append({"path": full_path, "duration": dur})
                else:
                    seen[norm] = [{"path": full_path, "duration": dur}]

            # --- Album art processing ---
            artist, title = extract_metadata_from_filename(file)
            if not artist or not title:
                msg = f"⚠️ Skipping (invalid name): {file}"
                print(msg)
                log_lines.append(msg)
                stats["invalid_name"] += 1
                continue

            current_art = get_embedded_art(full_path)

            if current_art:
                stats["has_art"] += 1
                width, height = get_image_size(current_art)
                if width is None or height is None:
                    msg = f"⚠️ Corrupted art in: {file}"
                    print(msg)
                    log_lines.append(msg)
                    stats["corrupted_art"] += 1
                    continue
                if width == MAX_SIZE and height == MAX_SIZE:
                    msg = f"✅ Already correct size: {file}"
                    print(msg)
                    log_lines.append(msg)
                    continue
                elif width < MAX_SIZE or height < MAX_SIZE:
                    msg = f"🖼 Too small, replacing with iTunes art: {file}"
                    print(msg)
                    log_lines.append(msg)
                    new_art = download_album_art(artist, title)
                    if new_art:
                        embed_album_art(full_path, new_art)
                        stats["replaced_small"] += 1
                    else:
                        msg = f"❌ Could not download art for: {file}"
                        print(msg)
                        log_lines.append(msg)
                        stats["download_failed"] += 1
                else:
                    msg = f"🔧 Resizing large art: {file} ({width}x{height})"
                    print(msg)
                    log_lines.append(msg)
                    embed_album_art(full_path, current_art)
                    stats["resized"] += 1

            else:
                msg = f"🎵 No album art found, downloading for: {artist} - {title}"
                print(msg)
                log_lines.append(msg)
                new_art = download_album_art(artist, title)
                if new_art:
                    embed_album_art(full_path, new_art)
                    stats["added_missing"] += 1
                else:
                    msg = f"❌ No album art found online for: {file}"
                    print(msg)
                    log_lines.append(msg)
                    stats["download_failed"] += 1

    # --- Summary ---
    summary_lines = [
        "",
        "--- Summary ---",
        f"🎧 Total MP3 files checked: {stats['total_checked']}",
        f"🖼  Already had album art: {stats['has_art']}",
        f"🔧 Resized (too large): {stats['resized']}",
        f"🪄 Replaced small art: {stats['replaced_small']}",
        f"🎨 Added missing art: {stats['added_missing']}",
        f"⚠️ Invalid names skipped: {stats['invalid_name']}",
        f"❌ Downloads failed: {stats['download_failed']}",
        f"💾 Corrupted images: {stats['corrupted_art']}",
    ]

    print("\n".join(summary_lines))
    log_lines.extend(summary_lines)

    # --- Duplicate summary ---
    if duplicates:
        print("\n--- Possible duplicates detected ---")
        log_lines.append("\n--- Possible duplicates detected ---")
        for a, b in duplicates:
            line = f"🔁 {os.path.basename(a)}  <>  {os.path.basename(b)}"
            print(line)
            log_lines.append(line)
        print(f"Total duplicate pairs: {len(duplicates)}")
        log_lines.append(f"Total duplicate pairs: {len(duplicates)}")
    else:
        print("\nNo duplicates found.")
        log_lines.append("No duplicates found.")

    # --- Save log ---
    if ENABLE_LOGGING:
        save_log(folder_path, log_lines)

# --- Main entry point ---
def main():
    Tk().withdraw()
    folder = filedialog.askdirectory(title="Select your music folder")
    if folder:
        process_folder(folder)
    else:
        print("❌ No folder selected.")

if __name__ == "__main__":
    main()
