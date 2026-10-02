# agents_bhakti/bhakti_pipeline.py
"""Bhakti pipeline v2 orchestration (spec sections 25, 27, 28, 29).

Split in two so scheduler_bhakti.py keeps its existing intelligence stages
(saturation, comparison, A/B title, SEO, thumbnail) in the middle:

  build_story_job(topic, comparison)  research -> story -> retention -> scenes
  build_video(job, log)               visuals -> voice -> music/sfx -> captions
                                      -> compose -> mix -> QA (+scene repair)

Every stage degrades gracefully; the scheduler falls back to the legacy
renderer if build_video raises.
"""

import os

from agents_bhakti.bhakti_types import VideoJob

class QAGateFailed(RuntimeError):
    """Video rendered but did not clear the publish gate - must NOT be uploaded."""


MAX_STORY_ATTEMPTS = int(os.environ.get("BHAKTI_MAX_STORY_ATTEMPTS", "2"))
MAX_REPAIR_ROUNDS = int(os.environ.get("BHAKTI_MAX_REPAIR_ROUNDS", "1"))
ENFORCE_QA_GATE = os.environ.get("BHAKTI_ENFORCE_QA_GATE", "true").lower() == "true"


def build_story_job(topic, comparison_insights=None, log=print):
    from agents_bhakti.bhakti_research_agent import research_bhakti_topic
    from agents_bhakti.bhakti_story_agent import generate_story
    from agents_bhakti.bhakti_retention_agent import evaluate_retention
    from agents_bhakti.bhakti_scene_agent import create_scene_plan

    job = VideoJob(topic=topic)
    job.research = research_bhakti_topic(topic)
    log(f"Research: deity={job.research.get('deity')} event={job.research.get('main_event')}")

    feedback, best = None, None
    for attempt in range(1, MAX_STORY_ATTEMPTS + 1):
        script = generate_story(topic, job.research, comparison_insights, feedback)
        retention = evaluate_retention(script, job.research)
        log(f"Retention attempt {attempt}: avg={retention['average']} approved={retention['approved']} "
            f"{retention.get('problems') or ''}")
        if best is None or retention["average"] > best[1]["average"]:
            best = (script, retention)
        if retention["approved"]:
            break
        feedback = retention.get("feedback")
    job.script, job.retention = best     # best attempt wins even if none cleared the bar

    job.scenes = create_scene_plan(job.script, job.research)
    log(f"Scene plan: {len(job.scenes)} scenes "
        f"({', '.join(s.purpose for s in job.scenes)})")
    return job


def _allow_ai_deity():
    # The repo's channel policy is "no AI-generated deity depictions". The spec's hybrid
    # strategy is supported structurally (scene.needs_ai) but stays OFF unless enabled.
    return os.environ.get("BHAKTI_ALLOW_AI_DEITY", "false").lower() == "true"


def build_video(job, log=print, title=""):
    from agents_bhakti.bhakti_voice_agent import generate_bhakti_voice
    from agents_bhakti.bhakti_visual_agent import fetch_scene_clips
    from agents_bhakti.bhakti_music_agent import select_devotional_music, music_timeline
    from agents_bhakti.bhakti_sfx_agent import generate_sfx_plan
    from agents_bhakti.bhakti_caption_agent import generate_captions
    from agents_bhakti.bhakti_audio_agent import mix_audio, LEAD_IN, TAIL
    from agents_bhakti.bhakti_video_agent import compose_video
    from agents_bhakti.bhakti_qa_agent import run_quality_check

    # Voice first: it fixes real per-scene timings that visuals, captions, SFX and music follow.
    log("Voice direction + per-scene Hindi TTS...")
    job.voice_path, job.voice_segments = generate_bhakti_voice(job.scenes, job.script)

    ai_scenes = [s.scene_id for s in job.scenes if s.needs_ai]
    if ai_scenes and not _allow_ai_deity():
        log(f"Scenes {ai_scenes} flagged for AI imagery — using symbolic stock footage (policy: no AI deities)")
    elif ai_scenes:
        log(f"Scenes {ai_scenes} flagged needs_ai: AI generation hook not implemented yet — using stock fallback")

    log("Pexels search + ranking per scene...")
    failures = fetch_scene_clips(job.scenes)
    if failures:
        raise RuntimeError(f"No suitable Pexels clip for scenes {failures}")

    log("Music + SFX...")
    job.music = select_devotional_music(job.research, job.scenes, title)
    if not job.music:
        raise RuntimeError("No background music track found — aborting rather than uploading a silent video")
    job.sfx = generate_sfx_plan(job.scenes)
    job.audio_path, total, lead = mix_audio(job.voice_path, job.music["path"],
                                            music_timeline(job.scenes), job.sfx)
    log(f"Audio mixed: {total:.1f}s, {len(job.sfx)} SFX")

    job.captions_path = generate_captions(job.scenes, job.voice_segments, lead)

    for round_no in range(MAX_REPAIR_ROUNDS + 1):
        log("Rendering cinematic edit..." if round_no == 0 else f"Re-rendering after repair #{round_no}...")
        job.final_video = compose_video(job.scenes, job.audio_path, job.captions_path, lead, TAIL)
        job.qa = run_quality_check(job, lead)
        log(f"QA: {job.qa['scores']} approved={job.qa['approved']} issues={job.qa['issues']}")
        if job.qa["approved"] or round_no == MAX_REPAIR_ROUNDS:
            break
        failed = set(job.qa["failed_scenes"])
        if not failed:
            break        # audio/caption/technical problems can't be fixed by swapping a clip
        log(f"Regenerating only scenes {sorted(failed)}")
        exclude = {s.scene_id: {s.clip_id} for s in job.scenes if s.scene_id in failed and s.clip_id}
        for s in job.scenes:
            if s.scene_id in failed:
                s.clip_path = s.clip_id = None
        fetch_scene_clips(job.scenes, exclude_by_scene=exclude, only=failed)
        if any(s.clip_path is None for s in job.scenes):
            break

    job.save()
    if ENFORCE_QA_GATE and not job.qa.get("approved"):
        raise QAGateFailed(f"QA gate failed: scores={job.qa.get('scores')} issues={job.qa.get('issues')}")
    return job
