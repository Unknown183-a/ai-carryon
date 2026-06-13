from gtts import gTTS
import os

def generate_voice(script):

    os.makedirs("output", exist_ok=True)

    voice_path = "output/voice.mp3"

    tts = gTTS(
        text=script,
        lang="en"
    )

    tts.save(voice_path)

    return voice_path