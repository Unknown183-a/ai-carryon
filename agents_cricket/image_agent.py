# agents_cricket/image_agent.py
"""Pexels stock footage only — generic cricket stadium/crowd/gameplay images,
never broadcast clips or team logos. Keeps this copyright-safe."""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

QUERIES = [
    "cricket stadium crowd",
    "cricket bat ball closeup",
    "cricket player celebration",
    "cricket stadium floodlights",
]


def generate_backgrounds(match_summary=None, num_images=4):
    folder = "assets/backgrounds"
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    pexels_key = os.getenv("PEXELS_API_KEY", "")
    image_paths, errors = [], []

    for i, query in enumerate(QUERIES[:num_images]):
        output_path = os.path.join(folder, f"{i+1}.jpg")
        try:
            headers = {"Authorization": pexels_key}
            params = {"query": query, "orientation": "portrait", "size": "large", "per_page": 1}
            r = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if data.get("photos"):
                img_url = data["photos"][0]["src"]["large2x"]
                img_r = requests.get(img_url, timeout=60)
                img_r.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(img_r.content)
                image_paths.append(output_path)
            else:
                errors.append(f"No Pexels result for '{query}'")
        except Exception as e:
            errors.append(f"Image {i+1} failed: {e}")

    return image_paths, errors
