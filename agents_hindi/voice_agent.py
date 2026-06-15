# agents_hindi/voice_agent.py
import asyncio
import edge_tts
import os

# Best Hindi voices
HINDI_VOICES = [
    "hi-IN-MadhurNeural",    # Male - clear and natural
    "hi-IN-SwaraNeural",     # Female - warm and engaging
]

VOICE = HINDI_VOICES[0]  # Use Madhur (male) by default

async def _generate(script, output_path):
    communicate = edge_tts.Communicate(script, VOICE)
    await communicate.save(output_path)

def generate_voice(script):
    os.makedirs("output", exist_ok=True)
    output_path = "output/voice.mp3"
    asyncio.run(_generate(script, output_path))
    print(f"Hindi voice generated: {output_path}")
    return output_path
