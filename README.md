# MP3 Album Art Tool

Simple tool to manage album art in MP3 files. It will attempt to resize existing embedded covers (if larger than MAX_SIZE) or download missing covers from the iTunes Search API and embed them into MP3 files using ID3v2.3 APIC tags.

## Features
- Resize embedded album artwork to a configurable maximum pixel size.
- Download missing artwork from iTunes using Artist + Title tags.
- Save artwork as JPEG in ID3v2.3 APIC tag.
- Recursively processes folders and prints a summary of results.

## Requirements
- Python 3.7+
- Libraries:
  - requests
  - pillow
  - mutagen

Install dependencies:
```sh
pip install requests pillow mutagen
```

## Usage
Run the script and choose a folder when the dialog opens:
```sh
python app.py
```
The script will:
- Walk the selected folder recursively.
- For each .mp3: resize existing embedded artwork if larger than MAX_SIZE, or try to download and embed artwork if missing.
- Print per-file status and final statistics.

## Configuration
- MAX_SIZE constant in the script controls the maximum artwork dimension in pixels (default: 400).
- The iTunes artwork URL is requested at higher resolution (default code uses 600x600) before resizing.

## How it works (high level)
1. Read ID3 tags (TPE1 = artist, TIT2 = title).
2. If APIC tag exists: extract image, resize if needed, re-embed.
3. If no APIC: query iTunes for the best match, download higher-resolution artwork, resize and embed.
4. Save tags as ID3v2.3.

## Output & Statistics
The script prints:
- Files processed
- Counts of resized / added / missing / skipped
- Lists of files where artwork was not found or files skipped due to missing tags or errors

## Troubleshooting
- If iTunes requests fail, check internet connectivity.
- If files cannot be modified, verify file permissions.
- If artist or title tags are missing, the script will skip that file.

## License
[MIT License](https://github.com/rol2005hun/golf7-album-art-tool?tab=MIT-1-ov-file)
