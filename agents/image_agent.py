# agents/image_agent.py
import requests
import os
import re
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")


def generate_image_prompts(topic, script, num_images=4):
    prompt = (
        f"You are a visual director for YouTube Shorts videos.\n\n"
        f"Topic: {topic}\n"
        f"Script excerpt: {script[:300]}\n\n"
        "Generate 4 AI image generation prompts for background images.\n\n"
        "RULES:\n"
        "- Each prompt DIRECTLY matches the topic\n"
        "- Style: cinematic, dramatic lighting, 9:16 vertical\n"
        "- Example: Apple Siri AI -> holographic Siri interface glowing blue futuristic\n"
        "- Example: LangChain -> Python code chains connecting AI models neon glow dark\n"
        "- Example: Bitcoin crash -> bitcoin coin falling red graph dramatic lighting\n"
        "- NO generic tech images, NO random people\n"
        "- Each prompt: 10-15 words, vivid and specific\n\n"
        "Return ONLY a numbered list:\n"
        "1. <prompt>\n"
        "2. <prompt>\n"
        "3. <prompt>\n"
        "4. <prompt>"
    )

    response = llm.invoke(prompt).content

    lines = []
    for line in response.split("\n"):
        line = line.strip()
        import re as _re
        match = _re.match(r"^\d+\.\s*(.+)", line)
        if match:
            lines.append(match.group(1).strip())

    if not lines:
        words = topic.replace("||PATTERN:", "").split()[:4]
        lines = [" ".join(words) + " cinematic dramatic"] * num_images

    return lines[:num_images]


def download_generated_image(prompt, output_path):
    import re as _re
    clean_prompt = _re.sub(r"[^a-zA-Z0-9 ,]", "", prompt).strip()
    encoded = requests.utils.quote(clean_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&nologo=true&enhance=true"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(response.content)
    return output_path


def generate_backgrounds(topic, script, num_images=4):
    folder = "assets/backgrounds"
    os.makedirs(folder, exist_ok=True)

    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    clean_topic = topic.split("||PATTERN:")[0].strip()
    prompts = generate_image_prompts(clean_topic, script, num_images)

    print(f"\nGenerated prompts for: {clean_topic}")
    for i, p in enumerate(prompts):
        print(f"  {i+1}: {p}")

    image_paths = []
    errors = []
    for i, prompt in enumerate(prompts):
        output_path = os.path.join(folder, f"{i+1}.jpg")
        try:
            download_generated_image(prompt, output_path)
            image_paths.append(output_path)
            print(f"Image {i+1}: generated and saved")
        except Exception as e:
            errors.append(f"Image {i+1}: {e}")
            print(f"Image {i+1} failed: {e}")

    return image_paths, errors
