# agents/manim_agent.py
import os
import subprocess
import re
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")


def generate_manim_code(topic, script):
    prompt = f"""
You are a Manim animation expert. Write a Manim Python script for this YouTube Shorts topic.

Topic: {topic}
Script summary: {script[:300]}

STRICT RULES — violations will cause crashes:
- Class name must be EXACTLY: VideoScene
- Use dark background: self.camera.background_color = "#0a0a0a"
- Total animation duration: 45-55 seconds
- ONLY use these animations: Write, FadeIn, FadeOut, Create
- ONLY use these objects: Text, Circle, Rectangle, Arrow, VGroup, Line
- NO MathTex, NO Tex, NO LaTeX math
- NO emojis anywhere
- Colors: YELLOW, WHITE, GREEN, BLUE, RED, ORANGE only
- shift() takes ONLY direction: .shift(DOWN) or .shift(UP*2) — NO buff argument
- next_to() is fine: .next_to(obj, DOWN, buff=0.5)
- animate.shift() takes ONLY direction: group.animate.shift(DOWN*2) — NO buff
- Always position objects BEFORE playing them
- Keep it simple — max 15 animations total

Return ONLY the Python code, no explanation, no markdown backticks.
"""

    response = llm.invoke(prompt).content
    code = response.strip()
    code = re.sub(r'^```python\n?', '', code)
    code = re.sub(r'^```\n?', '', code)
    code = re.sub(r'\n?```$', '', code)

    # Auto-fix common Groq mistakes
    # Fix shift with buff argument
    code = re.sub(r'\.shift\(([^,)]+),\s*buff=[^)]+\)', r'.shift(\1)', code)
    code = re.sub(r'animate\.shift\(([^,)]+),\s*buff=[^)]+\)', r'animate.shift(\1)', code)

    return code.strip()


def render_manim_animation(topic, script, attempt=1):
    os.makedirs("output/manim", exist_ok=True)

    print(f"Generating Manim code (attempt {attempt})...")
    code = generate_manim_code(topic, script)

    code_path = "output/manim/scene.py"
    with open(code_path, "w") as f:
        f.write(code)

    print("Rendering Manim animation...")

    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~')}/Library/TinyTeX/bin/universal-darwin:" + env.get("PATH", "")

    try:
        result = subprocess.run(
            ["manim", "-ql", "--format=mp4", code_path, "VideoScene"],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd="/Users/amit/Desktop/AI carryON"
        )

        if result.returncode != 0:
            print(f"Manim error (attempt {attempt}):\n{result.stderr[-500:]}")

            # Retry once with simpler prompt
            if attempt < 3:
                return render_manim_animation(topic, script, attempt + 1)
            return None

        # Find output file
        for root, dirs, files in os.walk("output/manim"):
            for f in files:
                if f.endswith(".mp4") and "VideoScene" in f:
                    return os.path.join(root, f)

        print("Could not find rendered video")
        return None

    except subprocess.TimeoutExpired:
        print("Manim timed out")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None
