# agents/pipeline.py
from langchain_core.runnables import RunnableLambda

def step_research(inputs: dict) -> dict:
    from agents.research_agent import research
    print("🔍 Researching topic...")
    inputs["research"] = research(inputs["topic"])
    return inputs

def step_script(inputs: dict) -> dict:
    from agents.script_agent import create_script
    print("✍️  Writing script...")
    inputs["script"] = create_script(inputs["research"])
    return inputs

def step_seo(inputs: dict) -> dict:
    from agents.seo_agent import generate_seo
    print("📈 Generating SEO...")
    inputs["seo"] = generate_seo(inputs["topic"], inputs["script"])
    return inputs

def step_thumbnail(inputs: dict) -> dict:
    from agents.thumbnail_generator import generate_thumbnail
    print("🖼️  Generating thumbnail...")
    inputs["thumbnail"] = generate_thumbnail(inputs["seo"]["title"], inputs["topic"])
    return inputs

def step_images(inputs: dict) -> dict:
    from agents.image_agent import generate_backgrounds
    print("🌆 Fetching dark tech images...")
    paths, errors = generate_backgrounds(inputs["topic"], inputs["script"], num_images=4)
    if not paths:
        raise ValueError(f"Image generation failed: {errors}")
    inputs["image_paths"] = paths
    return inputs

def step_voice(inputs: dict) -> dict:
    from agents.voice_agent import generate_voice
    print("🎙️  Generating voiceover...")
    inputs["voice"] = generate_voice(inputs["script"])
    return inputs

def step_captions(inputs: dict) -> dict:
    from agents.caption_agent import create_srt
    print("💬 Generating captions...")
    inputs["captions"] = create_srt(inputs["script"], inputs["voice"])
    return inputs

def step_video(inputs: dict) -> dict:
    from agents.video_agent import create_video
    print("🎬 Creating video...")
    inputs["video"] = create_video()
    return inputs

def step_upload_youtube(inputs: dict) -> dict:
    from agents.upload_agent import upload_video
    print("📤 Uploading to YouTube...")
    seo = inputs["seo"]
    video_id, video_url = upload_video(
        video_path=inputs["video"],
        title=seo["title"],
        description=seo["description"],
        hashtags=seo["hashtags"],
        thumbnail_path=inputs["thumbnail"]
    )
    inputs["youtube_url"] = video_url
    inputs["youtube_id"] = video_id
    print(f"✅ YouTube: {video_url}")
    return inputs

def build_pipeline(upload=True):
    steps = [
        RunnableLambda(step_research),
        RunnableLambda(step_script),
        RunnableLambda(step_seo),
        RunnableLambda(step_thumbnail),
        RunnableLambda(step_images),
        RunnableLambda(step_voice),
        RunnableLambda(step_captions),
        RunnableLambda(step_video),
    ]
    if upload:
        steps.append(RunnableLambda(step_upload_youtube))

    pipeline = steps[0]
    for step in steps[1:]:
        pipeline = pipeline | step
    return pipeline

def run_pipeline(topic: str, upload: bool = True) -> dict:
    pipeline = build_pipeline(upload=upload)
    return pipeline.invoke({"topic": topic})
