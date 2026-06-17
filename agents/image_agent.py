# agents/image_agent.py
import requests
import os
import re
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")


def generate_image_queries(topic, script, num_images=4):
    prompt = f"""You are a visual director for YouTube Shorts videos.

Topic: {topic}
Script: {script}

Your job: extract {num_images} highly specific, visual search queries for stock photos that will appear as background images in this video.

Rules:
- Each query must directly relate to the topic — if the topic is about OpenAI, search for "AI neural network visualization", "tech company office", "robot hand keyboard" etc.
- Queries must describe something VISUALLY interesting and attention-grabbing
- Do NOT use generic queries like "technology background" or "abstract digital"
- Think like a video editor — what image would make a viewer stop scrolling?
- Each query: 3-5 words, concrete and specific
- Vary the queries — different visual angles of the same topic

Return ONLY a numbered list, one query per line, nothing else:
1. <query>
2. <query>
3. <query>
4. <query>"""

    response = llm.invoke(prompt).content

    lines = []
    for line in response.split("\n"):
        line = line.strip()
        match = re.match(r"^\d+\.\s*(.+)", line)
        if match:
            lines.append(match.group(1).strip())

    if not lines:
        words = topic.replace("||PATTERN:", "").split()[:3]
        lines = [" ".join(words)] * num_images

    return lines[:num_images]


def download_image(query, output_path):
    clean_query = re.sub(r"[^a-zA-Z0-9\s]", "", query).strip()
    if not clean_query:
        clean_query = "artificial intelligence technology"

    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={clean_query}&orientation=portrait&per_page=5"

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data.get("photos"):
        fallback = clean_query.split()[0] + " technology"
        url = f"https://api.pexels.com/v1/search?query={fallback}&orientation=portrait&per_page=3"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

    if not data.get("photos"):
        raise ValueError(f"No photos found for: {query}")

    photos = data["photos"]
    best = max(photos, key=lambda p: p["width"] * p["height"])
    image_url = best["src"]["portrait"]

    img_response = requests.get(image_url, timeout=30)
    img_response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(img_response.content)

    return output_path


def generate_backgrounds(topic, script, num_images=4):
    folder = "assets/backgrounds"
    os.makedirs(folder, exist_ok=True)

    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    if not PEXELS_API_KEY:
        return [], ["PEXELS_API_KEY not set in .env file"]

    clean_topic = topic.split("||PATTERN:")[0].strip()

    queries = generate_image_queries(clean_topic, script, num_images)

    image_paths = []
    errors = []
    for i, query in enumerate(queries):
        output_path = os.path.join(folder, f"{i+1}.jpg")
        try:
            download_image(query, output_path)
            image_paths.append(output_path)
            print(f"Image {i+1}: '{query}' -> saved")
        except Exception as e:
            errors.append(f"Image {i+1} ({query}): {e}")
            print(f"Image {i+1} failed: {e}")

    return image_paths, errors
