# agents_bhakti/voice_agent.py
import os
import base64

# Sarvam AI voices — primary + fallback (Bulbul v3). Same voice pool as the
# Hindi channel; devotional tone comes from a slower pace + lower
# temperature (calmer, less "hyped") rather than a different speaker.
PRIMARY_SPEAKER = "vijay"
FALLBACK_SPEAKER = "shubh"

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")


def _generate_sarvam(script, output_path, speaker):
    """Generate voice using Sarvam AI Bulbul v3 — native Indian Hindi voice,
    slowed and steadied for a devotional/narration tone."""
    from sarvamai import SarvamAI
    from pydub import AudioSegment
    import io

    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

    text = script[:2500]

    audio = client.text_to_speech.convert(
        text=text,
        language_code="hi-IN",
        speaker=speaker,
        model="bulbul:v3",
        pace=0.92,          # slightly slower than the tech channel — calmer, devotional pacing
        temperature=0.5,    # steadier, less variation than the hyped tech-channel voice
    )

    print(f"Sarvam returned {len(audio.audios)} audio segment(s)")

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
        # -15% rate for a calmer devotional pace than the default tech-channel fallback
        communicate = edge_tts.Communicate(script, "hi-IN-MadhurNeural", rate="-15%")
        await communicate.save(output_path)

    asyncio.run(_gen())


def generate_voice(script):
    os.makedirs("output", exist_ok=True)
    output_path = "output/voice.mp3"

    if not SARVAM_API_KEY:
        print("SARVAM_API_KEY not set — using edge-tts fallback")
        _generate_edge_tts_fallback(script, output_path)
        return output_path

    try:
        _generate_sarvam(script, output_path, PRIMARY_SPEAKER)
        print(f"Bhakti voice generated (Sarvam/{PRIMARY_SPEAKER}): {output_path}")
        return output_path
    except Exception as e:
        print(f"Primary speaker ({PRIMARY_SPEAKER}) failed: {e}")

    try:
        _generate_sarvam(script, output_path, FALLBACK_SPEAKER)
        print(f"Bhakti voice generated (Sarvam/{FALLBACK_SPEAKER}): {output_path}")
        return output_path
    except Exception as e:
        print(f"Fallback speaker ({FALLBACK_SPEAKER}) failed: {e}")

    print("Sarvam AI unavailable — using edge-tts fallback")
    _generate_edge_tts_fallback(script, output_path)
    return output_path
