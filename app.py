import os
import io
import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from PIL import Image
from collections import defaultdict
from tkinter import Tk, filedialog

MAX_SIZE = 400  # maximum album cover size (px)

def download_album_art(artist, title, size=600):
    # Download album cover from iTunes API
    query = f"{artist} {title}"
    url = "https://itunes.apple.com/search"
    params = {"term": query, "media": "music", "limit": 1}
    resp = requests.get(url, params=params)

    if resp.status_code != 200:
        print("❌ Failed to connect to iTunes API")
        return None

    results = resp.json().get("results")
    if not results:
        print("⚠️ No results found on iTunes")
        return None

    art_url = results[0].get("artworkUrl100")
    if not art_url:
        print("⚠️ No artwork URL found")
        return None

    # Request higher resolution (100x100 → 600x600)
    art_url = art_url.replace("100x100", f"{size}x{size}")

    print(f"⬇️ Downloading artwork: {art_url}")
    img_data = requests.get(art_url).content
    return img_data

def resize_image(data):
    # Resize the image if it's larger than MAX_SIZE
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        if max(img.size) <= MAX_SIZE:
            print("📏 Image already within acceptable size, skipping resize.")
            return data
        img.thumbnail((MAX_SIZE, MAX_SIZE))
        out = io.BytesIO()
        img.save(out, format="JPEG")
        return out.getvalue()

def process_mp3(filepath):
    try:
        audio = MP3(filepath, ID3=ID3)
        tags = ID3(filepath)
        apic_tags = [tag for key, tag in tags.items() if key.startswith("APIC")]

        if apic_tags:
            print("🎨 Album cover found, resizing...")
            art = apic_tags[0].data
            resized = resize_image(art)
            status = "resized"
        else:
            print("⚠️ No album cover found, downloading...")
            artist = tags.get("TPE1")
            title = tags.get("TIT2")
            if not artist or not title:
                print("⚠️ Missing artist or title tag — cannot search for artwork")
                return "skipped"

            art = download_album_art(str(artist), str(title))
            if not art:
                print("⚠️ Could not find album artwork")
                return "missing"

            resized = resize_image(art)
            status = "added"

        tags.delall("APIC")
        tags.add(APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,
            desc="Cover",
            data=resized
        ))
        tags.save(v2_version=3)
        print(f"✅ Album art saved ({status})")
        return status

    except error as e:
        print(f"❌ Error: {e}")
        return "skipped"

def main():
    # Select folder
    root = Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select the folder containing your music files")
    if not folder:
        print("🚫 No folder selected, exiting.")
        return

    print(f"📁 Selected folder: {folder}")
    format_counter = defaultdict(int)

    # Statistics containers
    stats = {"resized": [], "added": [], "missing": [], "skipped": []}

    # Recursively walk through files
    for dirpath, _, filenames in os.walk(folder):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            format_counter[ext] += 1

            if ext == ".mp3":
                filepath = os.path.join(dirpath, filename)
                print(f"\n🎵 Processing: {filepath}")
                status = process_mp3(filepath)
                if status:
                    stats[status].append(filepath)

    # File type statistics
    print("\n📊 File type statistics:")
    for ext, count in sorted(format_counter.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ext or 'No extension'}: {count} file(s)")

    # Processing statistics
    print("\n📊 Processing results:")
    print(f"  Resized covers: {len(stats['resized'])}")
    print(f"  Added covers: {len(stats['added'])}")
    print(f"  Failed (no results): {len(stats['missing'])}")
    print(f"  Skipped (missing tags / error): {len(stats['skipped'])}")

    # Detailed lists
    if stats["missing"]:
        print("\n❌ No album cover found for these files:")
        for f in stats["missing"]:
            print(f"   {f}")

    if stats["skipped"]:
        print("\n⚠️ Skipped files:")
        for f in stats["skipped"]:
            print(f"   {f}")

if __name__ == "__main__":
    main()
