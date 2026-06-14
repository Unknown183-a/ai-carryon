import requests
import os
import re
from dotenv import load_dotenv
load_dotenv()


def generate_image_prompts(topic, script, num_images=4):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    prompt = f"""
    Based on this topic and script, create {num_images} short search keywords (2-4 words each)
    for finding relevant stock photos. Keywords should describe visual, tech-related scenes.

    Topic: {topic}
    Script: {script}

    Return ONLY a numbered list, one keyword phrase per line, no extra text.
    """
    response = llm.invoke(prompt).content
    lines = []
    for line in response.split("\n"):
        line = line.strip()
        match = re.match(r"^\d+\.\s*(.+)", line)
        if match:
            lines.append(match.group(1).strip())
    if not lines:
        lines = [topic] * num_images
    return lines[:num_images]


def download_image(query, output_path):
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&orientation=portrait&per_page=1"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("photos"):
        raise ValueError(f"No photos found for query: {query}")
    image_url = data["photos"][0]["src"]["portrait"]
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
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    if not PEXELS_API_KEY:
        return [], ["PEXELS_API_KEY not set"]
    # Clean topic - remove hashtags before generating prompts
    clean_topic = topic.replace("#", "").split()[0] if topic else "technology"
    queries = generate_image_prompts(clean_topic, script, num_images)
    image_paths = []
    errors = []
    for i, query in enumerate(queries):
        output_path = os.path.join(folder, f"{i+1}.jpg")
        try:
            download_image(query, output_path)
            image_paths.append(output_path)
        except Exception as e:
            errors.append(f"Image {i+1} ({query}): {e}")
    return image_paths, errors