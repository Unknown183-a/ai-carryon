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
    for finding dark, dramatic, cinematic tech stock photos.

    Topic: {topic}
    Script: {script}

    Rules:
    - Every keyword must be dark/moody themed
    - Focus on tech visuals: circuits, code, screens, servers, chips, neon, cyber
    - Add "dark" or "neon" or "cinematic" to each phrase
    - Examples: "dark circuit board", "neon code screen", "dark server room", "cyber technology dark"

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
        lines = [f"dark {topic} technology"] * num_images
    return lines[:num_images]


def download_image(query, output_path):
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    headers = {"Authorization": PEXELS_API_KEY}

    # Try portrait first, fallback to landscape
    for orientation in ["portrait", "landscape"]:
        url = f"https://api.pexels.com/v1/search?query={query}&orientation={orientation}&per_page=5"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("photos"):
            # Pick darkest looking image (just pick randomly from top 5)
            import random
            photo = random.choice(data["photos"])
            image_url = photo["src"]["portrait"] if orientation == "portrait" else photo["src"]["large2x"]
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(img_response.content)
            return output_path

    raise ValueError(f"No photos found for query: {query}")


# Fallback dark tech queries if AI fails
DARK_TECH_FALLBACKS = [
    "dark circuit board neon",
    "code screen dark background",
    "dark server room blue",
    "cyber technology neon dark",
    "dark computer chip closeup",
    "neon lights technology dark",
    "dark data center",
    "black technology abstract"
]


def generate_backgrounds(topic, script, num_images=4):
    folder = "assets/backgrounds"
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    if not PEXELS_API_KEY:
        return [], ["PEXELS_API_KEY not set"]

    clean_topic = topic.replace("#", "").split()[0] if topic else "technology"

    try:
        queries = generate_image_prompts(clean_topic, script, num_images)
    except Exception:
        import random
        queries = random.sample(DARK_TECH_FALLBACKS, num_images)

    image_paths = []
    errors = []

    for i, query in enumerate(queries):
        output_path = os.path.join(folder, f"{i+1}.jpg")
        try:
            download_image(query, output_path)
            image_paths.append(output_path)
        except Exception as e:
            # Fallback to a guaranteed dark tech query
            try:
                fallback_query = DARK_TECH_FALLBACKS[i % len(DARK_TECH_FALLBACKS)]
                download_image(fallback_query, output_path)
                image_paths.append(output_path)
            except Exception as e2:
                errors.append(f"Image {i+1} ({query}): {e2}")

    return image_paths, errors
