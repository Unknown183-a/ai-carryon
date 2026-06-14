# agents/manim_agent.py
import os
import subprocess
import tempfile
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

STRICT RULES:
- Class name must be EXACTLY: VideoScene
- Use dark background: self.camera.background_color = "#0a0a0a"
- Total animation duration: 45-55 seconds
- Use only: Text, Write, FadeIn, FadeOut, Create, Circle, Rectangle, Arrow, VGroup
- NO MathTex, NO Tex, NO LaTeX math (causes errors)
- NO emojis in Text() objects
- Colors: YELLOW, WHITE, GREEN, BLUE, RED, ORANGE
- Make it dynamic — text flying in, stats appearing, arrows connecting ideas
- Portrait orientation: use UP/DOWN positioning mostly
- End with a bold conclusion text

Return ONLY the Python code, no explanation, no markdown backticks.

Example structure:
from manim import *

class VideoScene(Scene):
    def construct(self):
        self.camera.background_color = "#0a0a0a"
        
        title = Text("TOPIC NAME", font_size=70, color=YELLOW, weight=BOLD)
        self.play(Write(title), run_time=1)
        self.wait(0.5)
        # ... more animations ...
"""

    response = llm.invoke(prompt).content
    
    # Clean up response — remove markdown if present
    code = response.strip()
    code = re.sub(r'^```python\n?', '', code)
    code = re.sub(r'^```\n?', '', code)
    code = re.sub(r'\n?```$', '', code)
    
    return code.strip()


def render_manim_animation(topic, script):
    """Generate and render Manim animation, return video path"""
    
    os.makedirs("output/manim", exist_ok=True)
    
    print("Generating Manim animation code with AI...")
    code = generate_manim_code(topic, script)
    
    # Save code to temp file
    code_path = "output/manim/scene.py"
    with open(code_path, "w") as f:
        f.write(code)
    
    print("Rendering Manim animation...")
    
    # Add TinyTeX to PATH for rendering
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~')}/Library/TinyTeX/bin/universal-darwin:" + env.get("PATH", "")
    
    try:
        result = subprocess.run(
            [
                "manim",
                "-ql",           # Low quality (480p) — faster
                "--format=mp4",
                code_path,
                "VideoScene"
            ],
            capture_output=True,
            text=True,
            timeout=300,         # 5 min timeout
            env=env,
            cwd="/Users/amit/Desktop/AI carryON"
        )
        
        if result.returncode != 0:
            print(f"Manim error: {result.stderr}")
            return None
            
        # Find the output file
        output_dir = "output/manim/media/videos/scene/480p15"
        if os.path.isdir(output_dir):
            files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
            if files:
                return os.path.join(output_dir, files[0])
        
        # Search more broadly
        for root, dirs, files in os.walk("output/manim"):
            for f in files:
                if f.endswith(".mp4") and "VideoScene" in f:
                    return os.path.join(root, f)
        
        print("Could not find rendered video file")
        return None
        
    except subprocess.TimeoutExpired:
        print("Manim rendering timed out")
        return None
    except Exception as e:
        print(f"Manim rendering failed: {e}")
        return None
