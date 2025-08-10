import os
import re
import requests
from bs4 import BeautifulSoup

# --- CONFIG ---
INPUT_HTML = "/Users/madhankrishnaperam/Downloads/dew_software/dewsoftware.txt"         # Original file from DewSoftware
OUTPUT_HTML = "index.html"             # New stripped-down HTML
IMG_DIR = "assets/images"              # Folder to store images

# Ensure image folder exists
os.makedirs(IMG_DIR, exist_ok=True)

# Read the original HTML
with open(INPUT_HTML, "r", encoding="utf-8") as f:
    html_content = f.read()

# Parse HTML
soup = BeautifulSoup(html_content, "html.parser")
image_urls = set()

# Extract images from <img> tags
for img in soup.find_all("img"):
    src = img.get("src")
    if src and not src.startswith("data:"):
        image_urls.add(src)

# Extract images from <style> tags
for style in soup.find_all("style"):
    matches = re.findall(r'url\(["\']?(.*?)["\']?\)', style.get_text())
    for url in matches:
        if not url.startswith("data:"):
            image_urls.add(url)

# Extract images from inline style attributes
for tag in soup.find_all(style=True):
    matches = re.findall(r'url\(["\']?(.*?)["\']?\)', tag["style"])
    for url in matches:
        if not url.startswith("data:"):
            image_urls.add(url)

# Download images and replace URLs with local paths
for url in image_urls:
    try:
        filename = os.path.basename(url.split("?")[0])  # remove query params
        filepath = os.path.join(IMG_DIR, filename)

        print(f"⬇ Downloading: {url}")
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(r.content)

        # Replace occurrences in the HTML
        html_content = html_content.replace(url, f"{IMG_DIR}/{filename}")
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")

# Parse again after replacements
soup = BeautifulSoup(html_content, "html.parser")

# ----- STRIP ORIGINAL CONTENT -----
# Replace all text nodes with placeholders
for tag in soup.find_all(text=True):
    if tag.strip() and not tag.parent.name in ["script", "style"]:
        tag.replace_with("[Placeholder]")

# Keep basic structure: header, main, footer
# Remove extra sections not needed for timesheet app mockup
allowed_tags = ["header", "nav", "main", "section", "footer", "div", "img", "h1", "h2", "h3", "p", "ul", "li", "button", "a"]
for tag in soup.find_all():
    if tag.name not in allowed_tags:
        tag.unwrap()

# ----- SAVE CLEANED HTML -----
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(str(soup))

print("\n✅ Done!")
print(f"Images saved in: {IMG_DIR}")
print(f"Updated stripped HTML saved as: {OUTPUT_HTML}")
