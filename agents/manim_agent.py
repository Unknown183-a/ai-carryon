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
- ALWAYS start with: from manim import *
- Class MUST inherit Scene: class VideoScene(Scene):
- Use dark background: self.camera.background_color = "#0a0a0a"
- NO Text() objects at all — captions are handled separately
- ONLY use: FadeIn, FadeOut, Create, GrowFromCenter
- ONLY use visual objects: Circle, Rectangle, Arrow, Line, Dot, Square, Star, VGroup
- Use colors and shapes to visually represent the topic (e.g. for AI: connected dots/nodes, for coding: rectangles representing code blocks)
- NO MathTex, NO Tex, NO LaTeX, NO Text
- Colors: YELLOW, WHITE, GREEN, BLUE, RED, ORANGE only
- shift() takes ONLY direction: .shift(DOWN) or .shift(UP*2)
- NO buff in shift(): WRONG: .shift(DOWN, buff=1) RIGHT: .shift(DOWN)
- animate needs an animation: WRONG: self.play(group.animate) RIGHT: self.play(group.animate.shift(DOWN))
- Always position objects BEFORE playing them
- Keep simple — max 10 animations total
- Total duration: 30-40 seconds
- Make it look like a dynamic abstract tech background

Return ONLY raw Python code, absolutely nothing else.
No markdown, no backticks, no explanation.
Start directly with: from manim import *
"""

    response = llm.invoke(prompt).content
    code = response.strip()

    # Remove markdown
    code = re.sub(r'^```python\n?', '', code)
    code = re.sub(r'^```\n?', '', code)
    code = re.sub(r'\n?```$', '', code)
    code = code.strip()

    # Auto-fix 1: Add missing import
    if "from manim import" not in code:
        code = "from manim import *\n\n" + code

    # Auto-fix 2: Fix class missing (Scene)
    code = re.sub(r'class VideoScene\s*:', 'class VideoScene(Scene):', code)

    # Auto-fix 3: Fix shift with buff
    code = re.sub(r'\.shift\(([^,)]+),\s*buff=[^)]+\)', r'.shift(\1)', code)
    code = re.sub(r'animate\.shift\(([^,)]+),\s*buff=[^)]+\)', r'animate.shift(\1)', code)

    # Auto-fix 4: Fix bare self.play(group.animate)
    code = re.sub(r'self\.play\((\w+)\.animate\)', r'# removed bad animate call', code)

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
            print(f"Manim error (attempt {attempt}):\n{result.stderr[-800:]}")
            if attempt < 3:
                return render_manim_animation(topic, script, attempt + 1)
            return None

        # Find output file - search multiple locations
        search_dirs = ["output/manim", "media", "."]
        for search_dir in search_dirs:
            if os.path.isdir(search_dir):
                for root, dirs, files in os.walk(search_dir):
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
