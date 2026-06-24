# agents/image_agent.py
import requests
import os
import re
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = get_llm()


def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile")
        llm.invoke("hi")
        return llm
    except Exception:
        return ChatGroq(model="llama3-8b-8192")


def generate_image_prompts(topic, script, num_images=4):
    prompt = (
        f"You are a visual director for YouTube Shorts.\n\n"
        f"Topic: {topic}\n"
        f"Script excerpt: {script[:300]}\n\n"
        "Generate 4 photorealistic image prompts showing ACTIVE DYNAMIC scenes directly about the topic.\n\n"
        "RULES:\n"
        "- Show people ACTIVELY DOING things: typing fast, laughing, pointing at screen, arguing, celebrating\n"
        "- Use motion words: leaning forward, gesturing, mid-sentence, hands moving, eyes focused\n"
        "- Each prompt must be DIRECTLY about the topic\n"
        "- ALWAYS end with: photorealistic, DSLR photo, 4K, motion blur, candid shot, natural lighting\n"
        "- Example: Claude AI coding -> software engineer leaning forward intensely typing Python code, multiple monitors glowing, photorealistic DSLR 4K candid\n"
        "- Example: Apple Siri -> person laughing while speaking to iPhone held up, Siri waveform visible on screen, photorealistic DSLR 4K candid\n"
        "- Example: team meeting -> executives pointing at whiteboard mid-discussion, engaged expressions, photorealistic DSLR 4K candid\n"
        "- Example: Bitcoin crash -> trader hands on head staring at red charts, shocked expression, photorealistic DSLR 4K candid\n"
        "- NO static poses, NO stock photo smiles, NO robots, NO neon sci-fi\n"
        "- Make it feel like a documentary photographer caught the moment\n\n"
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
        lines = [" ".join(words) + " photorealistic DSLR 4K candid"] * num_images

    return lines[:num_images]


def download_generated_image(prompt, output_path):
    import re as _re
    # Use Pexels as primary (reliable, no rate limit issues)
    pexels_key = os.getenv("PEXELS_API_KEY", "")
    if pexels_key:
        try:
            clean_prompt = _re.sub(r"[^a-zA-Z0-9 ,]", "", prompt).strip()
            # Extract key search terms (first 5 words)
            search_query = " ".join(clean_prompt.split()[:5])
            headers = {"Authorization": pexels_key}
            params = {"query": search_query, "orientation": "portrait", "size": "large", "per_page": 1}
            r = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if data.get("photos"):
                img_url = data["photos"][0]["src"]["large2x"]
                img_r = requests.get(img_url, timeout=60)
                img_r.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(img_r.content)
                return output_path
        except Exception as e:
            print(f"Pexels failed: {e}, trying pollinations...")

    # Fallback to pollinations.ai
    clean_prompt = _re.sub(r"[^a-zA-Z0-9 ,]", "", prompt).strip()
    encoded = requests.utils.quote(clean_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&nologo=true&enhance=true&model=flux"
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
