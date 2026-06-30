# agents_hindi/voice_agent.py
import os
import base64

# Sarvam AI voices — primary + fallback
PRIMARY_SPEAKER = "karun"
FALLBACK_SPEAKER = "hitesh"

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")


def _generate_sarvam(script, output_path, speaker):
    """Generate voice using Sarvam AI Bulbul v2 — native Indian Hindi voice.
    Sarvam splits long text into multiple audio chunks — concatenate ALL of them.
    Sarvam returns WAV — convert to MP3 to keep pipeline compatibility."""
    from sarvamai import SarvamAI
    from pydub import AudioSegment
    import io

    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

    text = script[:2500]

    audio = client.text_to_speech.convert(
        text=text,
        target_language_code="hi-IN",
        speaker=speaker,
    )

    print(f"Sarvam returned {len(audio.audios)} audio segment(s)")

    # Concatenate ALL audio segments — Sarvam splits long text into chunks
    combined = AudioSegment.empty()
    for i, audio_b64 in enumerate(audio.audios):
        wav_bytes = base64.b64decode(audio_b64)
        segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))
        combined += segment
        print(f"  Segment {i+1}: {len(segment)/1000:.1f}s")

    combined.export(output_path, format="mp3")
    print(f"Total combined audio: {len(combined)/1000:.1f}s")


def _generate_edge_tts_fallback(script, output_path):
    """Fallback to edge-tts if Sarvam fails (e.g. quota exceeded)."""
    import asyncio
    import edge_tts

    async def _gen():
        communicate = edge_tts.Communicate(script, "hi-IN-MadhurNeural")
        await communicate.save(output_path)

    asyncio.run(_gen())


def generate_voice(script):
    os.makedirs("output", exist_ok=True)
    output_path = "output/voice.mp3"  # unified path — convert WAV to MP3 internally

    if not SARVAM_API_KEY:
        print("SARVAM_API_KEY not set — using edge-tts fallback")
        output_path = "output/voice.mp3"
        _generate_edge_tts_fallback(script, output_path)
        return output_path

    # Try primary speaker
    try:
        _generate_sarvam(script, output_path, PRIMARY_SPEAKER)
        print(f"Hindi voice generated (Sarvam/{PRIMARY_SPEAKER}): {output_path}")
        return output_path
    except Exception as e:
        print(f"Primary speaker ({PRIMARY_SPEAKER}) failed: {e}")

    # Try fallback speaker
    try:
        _generate_sarvam(script, output_path, FALLBACK_SPEAKER)
        print(f"Hindi voice generated (Sarvam/{FALLBACK_SPEAKER}): {output_path}")
        return output_path
    except Exception as e:
        print(f"Fallback speaker ({FALLBACK_SPEAKER}) failed: {e}")

    # Final fallback to edge-tts
    print("Sarvam AI unavailable — using edge-tts fallback")
    output_path = "output/voice.mp3"
    _generate_edge_tts_fallback(script, output_path)
    return output_path
