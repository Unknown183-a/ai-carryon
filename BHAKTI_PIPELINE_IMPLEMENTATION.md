# 🕉️ AI CarryON — Bhakti Pipeline Implementation Specification

## Overview

The Bhakti pipeline is an automated short-form devotional video generation system designed to produce high-quality Hindi devotional content for YouTube Shorts.

The goal is **not** to generate repetitive AI slideshow videos.

The pipeline should create short devotional videos that feel like professionally edited cinematic content through:

- Relevant Pexels video footage
- Strong story hooks
- Natural Hindi narration
- Emotional voice direction
- Devotional background music
- Synchronized sound effects
- Cinematic video editing
- Dynamic captions
- Audio ducking and mixing
- Automated visual/audio quality control
- SEO and thumbnail generation

---

# 1. High-Level Architecture

```text
                         ┌──────────────────────┐
                         │   Topic Discovery    │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │   Bhakti Research    │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │ Hook + Story Agent   │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │    Retention Agent   │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │    Scene Planner     │
                         └──────────┬───────────┘
                                    ↓
                 ┌──────────────────┴──────────────────┐
                 ↓                                     ↓
       ┌────────────────────┐               ┌────────────────────┐
       │ Pexels Visual      │               │ Voice Direction    │
       │ Search + Ranking   │               │ + Hindi TTS        │
       └─────────┬──────────┘               └─────────┬──────────┘
                 ↓                                    ↓
       ┌────────────────────┐               ┌────────────────────┐
       │ Clip Processing    │               │ Voice Processing   │
       └─────────┬──────────┘               └─────────┬──────────┘
                 │                                    │
                 └────────────────┬───────────────────┘
                                  ↓
                         ┌──────────────────────┐
                         │ Music + SFX Agent    │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │ Video Composition    │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │ Caption Generation   │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │ Audio Mixing         │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │ Final QA Agent       │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │ Thumbnail + SEO      │
                         └──────────┬───────────┘
                                    ↓
                         ┌──────────────────────┐
                         │ YouTube Upload       │
                         └──────────────────────┘
```

---

# 2. Pipeline Stages

## Stage 1 — Topic Discovery

The system discovers potential Bhakti topics from:

- Current devotional trends
- Festival-related topics
- Search trends
- Popular devotional stories
- Mythological stories
- Interesting facts
- Lesser-known stories
- Devotional questions
- Stories involving Krishna, Shiva, Hanuman, Ram, Durga, Ganesh, etc.

### Topic categories

```text
Krishna
Shiva / Mahadev
Hanuman
Ram
Durga
Ganesh
Radha
Vishnu
Lakshmi
Saraswati
Bhakti Stories
Mythology
Temple Stories
Spiritual Facts
Festival Stories
Devotee Stories
```

The topic agent should avoid repeatedly selecting the same subject.

---

# 3. Bhakti Research Agent

Before writing the script, research the selected topic.

The research agent should identify:

```text
- Main story
- Important characters
- Location
- Historical/mythological context
- Key event
- Emotional moment
- Ending
- Important facts
```

The research output should be structured.

Example:

```json
{
  "topic": "Krishna and his devotee",
  "deity": "Krishna",
  "main_event": "Krishna protects his devotee",
  "emotion": "devotion",
  "setting": "ancient temple",
  "key_visuals": [
    "temple",
    "devotee praying",
    "storm",
    "divine light",
    "Krishna"
  ]
}
```

---

# 4. Hook + Story Agent

The script should be designed specifically for short-form video.

## Recommended structure

```text
0–3 sec     Hook
3–10 sec    Setup
10–20 sec   Conflict / Story
20–30 sec   Divine / Emotional Moment
30–40 sec   Resolution
40–45 sec   Emotional Ending / CTA
```

The exact duration can vary depending on the story.

### Hook examples

```text
"क्या आप जानते हैं भगवान कृष्ण ने अपने इस भक्त के लिए क्या किया था?"

"महादेव ने अपने इस भक्त की परीक्षा क्यों ली?"

"हनुमान जी के इस चमत्कार के पीछे की कहानी शायद आपने नहीं सुनी होगी।"
```

The hook should create curiosity without using misleading claims.

---

# 5. Retention Agent

The Retention Agent reviews the generated script before visual generation.

It checks:

```text
✓ Strong first 2–3 seconds
✓ No unnecessary introduction
✓ Story progresses continuously
✓ Emotional escalation
✓ Visual opportunities
✓ No excessive repetition
✓ Strong ending
✓ Appropriate duration
```

Example output:

```json
{
  "hook_score": 8,
  "story_score": 9,
  "emotional_score": 8,
  "visual_score": 9,
  "ending_score": 8,
  "approved": true
}
```

If the score is below the configured threshold:

```text
Script → Retention Agent → Regenerate
```

---

# 6. Scene Planner

The Scene Planner converts the script into individual visual scenes.

Each scene should contain:

```json
{
  "scene_id": 1,
  "start": 0,
  "end": 4,
  "purpose": "hook",
  "narration": "क्या आप जानते हैं...",
  "visual_description": "Ancient Indian temple during sunrise",
  "pexels_queries": [
    "Indian temple sunrise",
    "Hindu temple morning",
    "temple golden light"
  ],
  "camera": "slow push in",
  "mood": "mysterious",
  "music": "soft devotional",
  "sfx": ["temple_bell"]
}
```

This separates **story generation** from **visual generation**.

---

# 7. Pexels Visual Pipeline

## Important

The Bhakti pipeline will continue using **Pexels video clips as the primary visual source**.

Do not simply search one keyword and take the first result.

### Process

```text
Scene description
       ↓
Generate multiple search queries
       ↓
Pexels API
       ↓
Download candidate clips
       ↓
Filter by:
    - resolution
    - duration
    - orientation
    - relevance
       ↓
Rank clips
       ↓
Select best clip
```

---

# 8. Pexels Search Query Generation

For every scene, generate 3–5 related queries.

Example:

```text
Scene:
"Devotee praying to Krishna in a temple"

Queries:

1. Indian devotee praying temple
2. Hindu temple prayer
3. Krishna temple worship
4. Indian spiritual prayer
5. temple diya worship
```

This increases the probability of finding useful footage.

---

# 9. Clip Selection

Prefer:

```text
Vertical 9:16
↓
High resolution
↓
Clear subject
↓
Good lighting
↓
Stable footage
↓
Relevant content
```

Avoid:

```text
Low resolution
Watermarked footage
Extreme camera shake
Irrelevant people
Repeated clips
Poor lighting
Clips that conflict with narration
```

---

# 10. Cinematic Clip Processing

Raw Pexels footage should not simply be concatenated.

Apply scene-specific processing:

```text
Crop
Resize
Zoom
Pan
Speed adjustment
Color correction
Transitions
Blur
Light overlay
Particles
Vignette
Depth effects
```

Possible camera effects:

```text
slow_zoom_in
slow_zoom_out
pan_left
pan_right
vertical_pan
subtle_parallax
```

Effects should be subtle and depend on the scene.

---

# 11. Visual Continuity

The visual pipeline should avoid:

```text
Temple
→ random mountain
→ random woman
→ random river
→ unrelated temple
```

Instead, scenes should follow the story:

```text
Temple
 ↓
Devotee enters
 ↓
Devotee prays
 ↓
Problem occurs
 ↓
Environmental change
 ↓
Divine moment
 ↓
Resolution
```

This is one of the most important quality improvements.

---

# 12. Hybrid Visual Strategy

Pexels remains the default.

However, some mythological scenes may not have appropriate stock footage.

Use a hybrid approach:

```text
Real-world environment
        ↓
       Pexels

Specific mythological event
        ↓
    AI-generated
```

Examples:

| Scene | Source |
|---|---|
| Temple | Pexels |
| River | Pexels |
| Mountain | Pexels |
| Sunrise | Pexels |
| Devotee praying | Pexels |
| Incense / diya | Pexels |
| Festival | Pexels |
| Specific deity appearance | AI generation when needed |
| Divine transformation | AI generation when needed |
| Mythological event | AI generation when needed |

---

# 13. Hindi Voice Pipeline

The voice should sound like a **professional Hindi devotional narrator**, not a generic TTS system.

Voice generation should receive:

```json
{
  "text": "क्या आप जानते हैं...",
  "emotion": "mysterious",
  "speed": 0.95,
  "energy": 0.65,
  "pause_after": 0.4,
  "emphasis": [
    "भगवान कृष्ण",
    "अपने भक्त"
  ]
}
```

---

# 14. Voice Direction

Different parts of the story should use different delivery styles.

```text
HOOK
Energetic + curiosity

STORY
Warm + natural

CONFLICT
Serious + slightly slower

DIVINE MOMENT
Emotional + reverent

ENDING
Calm + devotional
```

Avoid:

```text
Robotic pacing
Same pitch throughout
No pauses
Overly fast narration
Excessive dramatic effects
Incorrect Hindi pronunciation
```

---

# 15. Voice Post-Processing

After TTS:

```text
Raw Voice
   ↓
Silence removal
   ↓
Noise reduction
   ↓
EQ
   ↓
Compression
   ↓
Loudness normalization
   ↓
Optional subtle reverb
   ↓
Final Voice
```

The voice should remain clearly understandable even when music and SFX are playing.

---

# 16. Devotional Music Pipeline

Music should be selected according to the story and deity.

Possible styles:

```text
Krishna
→ flute / bansuri / soft devotional

Shiva
→ damru / ambient / deep devotional

Hanuman
→ energetic devotional percussion

Ram
→ orchestral devotional / flute

Durga
→ powerful devotional percussion

Meditation
→ tanpura / ambient / bells
```

Avoid using the same background track for every video.

---

# 17. Dynamic Music Timeline

Music should change according to the story.

Example:

```text
0–3 sec
Ambient + subtle bell

3–12 sec
Soft devotional music

12–22 sec
Music gradually builds

22–30 sec
Emotional/divine peak

30–40 sec
Soft flute + bells
```

---

# 18. Sound Effects

Use subtle scene-specific SFX.

Possible effects:

```text
Temple bell
Conch
Diya/fire
Wind
Rain
River
Birds
Footsteps
Forest ambience
Crowd ambience
Divine chime
Thunder
```

SFX must support the scene instead of overpowering narration.

---

# 19. Audio Mixing

Final audio should contain three layers:

```text
VOICE
  ↓
MUSIC
  ↓
SFX
```

Voice is the priority.

Implement automatic ducking:

```text
When voice starts:
    Music volume ↓

When voice ends:
    Music volume ↑
```

Example conceptual levels:

```text
Voice       0 dB reference
Music       -16 to -22 dB
SFX         -18 to -26 dB
```

These are starting points and should be adjusted based on actual recordings.

---

# 20. Caption Engine

Captions should be designed for Shorts.

Avoid large blocks of text.

Instead:

```text
क्या आप जानते हैं...

भगवान कृष्ण

ने अपने भक्त की

कैसे रक्षा की?
```

Caption properties:

```text
Short phrases
Large readable font
High contrast
Correct Hindi rendering
Timed to narration
Important words emphasized
Subtle entrance animation
```

Do not animate every word excessively.

---

# 21. Video Composition

Recommended output:

```text
Resolution: 1080 × 1920
Aspect Ratio: 9:16
Format: MP4
Codec: H.264
Audio: AAC
FPS: 30
```

The final compositor combines:

```text
Pexels clips
+
Camera effects
+
Voice
+
Music
+
SFX
+
Captions
+
Transitions
```

---

# 22. Final QA Agent

Before upload, the video should automatically be checked.

## Visual QA

```text
✓ No black frames
✓ No corrupted clips
✓ No repeated clip unless intentional
✓ Correct 9:16 format
✓ Good brightness
✓ No extreme crop
✓ Scene matches narration
✓ No inappropriate footage
```

## Audio QA

```text
✓ Voice audible
✓ No clipping
✓ Music not overpowering
✓ No long silence
✓ SFX not overpowering
✓ Correct duration
```

## Caption QA

```text
✓ No spelling errors
✓ No text outside safe area
✓ Correct timing
✓ No overlapping captions
```

If a scene fails:

```text
QA
 ↓
Identify failed scene
 ↓
Regenerate only that scene
 ↓
Re-render
```

Do not regenerate the entire video unnecessarily.

---

# 23. Thumbnail Pipeline

Thumbnail generation should use:

```text
One strong subject
+
High contrast
+
Simple Hindi text
+
Emotional expression/visual
+
Strong devotional identity
```

Avoid putting the entire story into the thumbnail.

Example:

```text
कृष्ण ने
भक्त को क्यों बचाया?
```

---

# 24. SEO Pipeline

Generate:

```text
Title
Description
Hashtags
Tags
Keywords
```

Title should combine:

```text
Deity
+
Curiosity
+
Story
```

Example:

```text
श्री कृष्ण ने अपने भक्त की रक्षा कैसे की? 🙏 | Krishna Bhakti
```

Avoid misleading clickbait.

---

# 25. Recommended Internal Data Flow

The entire pipeline should pass structured objects instead of loose strings.

```python
VideoJob(
    topic=...,
    research=...,
    script=...,
    scenes=...,
    clips=...,
    voice=...,
    music=...,
    sfx=...,
    captions=...,
    final_video=...,
    qa=...
)
```

This makes the pipeline easier to debug and extend.

---

# 26. Suggested Agent Structure

```text
agents_hindi/
│
├── bhakti_topic_agent.py
├── bhakti_research_agent.py
├── bhakti_story_agent.py
├── bhakti_retention_agent.py
├── bhakti_scene_agent.py
├── bhakti_visual_agent.py
├── bhakti_voice_agent.py
├── bhakti_music_agent.py
├── bhakti_sfx_agent.py
├── bhakti_caption_agent.py
├── bhakti_video_agent.py
├── bhakti_audio_agent.py
├── bhakti_qa_agent.py
├── bhakti_thumbnail_agent.py
└── bhakti_upload_agent.py
```

If equivalent agents already exist, extend them instead of creating duplicate implementations.

---

# 27. Recommended Pipeline Function

Conceptually:

```python
def run_bhakti_pipeline():

    topic = discover_topic()

    research = research_bhakti_topic(topic)

    story = generate_story(
        topic=topic,
        research=research
    )

    retention = evaluate_retention(story)

    if not retention["approved"]:
        story = regenerate_story(
            topic,
            research,
            retention
        )

    scenes = create_scene_plan(story)

    clips = search_and_select_pexels_clips(
        scenes
    )

    processed_clips = process_clips(
        clips,
        scenes
    )

    voice = generate_hindi_voice(
        story,
        scenes
    )

    voice = process_voice(voice)

    music = select_devotional_music(
        story,
        scenes
    )

    sfx = generate_sfx_plan(
        scenes
    )

    captions = generate_captions(
        story,
        voice
    )

    video = compose_video(
        processed_clips,
        voice,
        music,
        sfx,
        captions
    )

    video = mix_audio(video)

    qa = run_quality_check(video)

    if not qa["approved"]:
        video = fix_failed_components(
            video,
            qa
        )

    thumbnail = generate_thumbnail(
        story
    )

    seo = generate_seo(
        story
    )

    upload_to_youtube(
        video=video,
        thumbnail=thumbnail,
        seo=seo
    )
```

---

# 28. Implementation Priority

Do not implement everything simultaneously.

## Phase 1 — Visual Quality

```text
1. Scene Planner
2. Better Pexels search
3. Clip ranking
4. Clip deduplication
5. Cinematic crop/zoom
6. Scene transitions
```

## Phase 2 — Voice

```text
7. Voice direction
8. Hindi pronunciation improvements
9. Voice post-processing
10. Automatic silence removal
11. Loudness normalization
```

## Phase 3 — Music

```text
12. Music selection
13. Music timeline
14. SFX selection
15. Audio ducking
16. Final audio mixing
```

## Phase 4 — Presentation

```text
17. Dynamic captions
18. Caption animations
19. Better thumbnail
20. SEO generation
```

## Phase 5 — Quality Control

```text
21. Visual QA
22. Audio QA
23. Caption QA
24. Scene-level regeneration
25. Final publish gate
```

---

# 29. Quality Gate

A video should only be uploaded if:

```text
Visual Quality       >= threshold
Voice Quality        >= threshold
Audio Quality        >= threshold
Story Quality        >= threshold
Caption Quality      >= threshold
Technical Quality    >= threshold
```

Conceptually:

```python
if (
    visual_score >= 8
    and voice_score >= 8
    and audio_score >= 8
    and story_score >= 8
    and caption_score >= 8
):
    upload()
else:
    repair()
```

The exact thresholds should be calibrated after testing.

---

# 30. Final Goal

The Bhakti pipeline should evolve from:

```text
Topic
 ↓
Pexels clips
 ↓
Voice
 ↓
Upload
```

into:

```text
                 STORY
                   ↓
                EMOTION
                   ↓
              SCENE PLAN
                   ↓
          ┌────────┴────────┐
          ↓                 ↓
       VISUAL             VOICE
          ↓                 ↓
       PEXELS            HINDI TTS
          ↓                 ↓
     EDITING             PROCESSING
          └────────┬────────┘
                   ↓
             MUSIC + SFX
                   ↓
              CAPTIONS
                   ↓
              AUDIO MIX
                   ↓
             FINAL VIDEO
                   ↓
                  QA
                   ↓
                UPLOAD
```

## Core Principle

> **Every element should serve the story.**

Pexels footage should support the narration.  
Voice should support the emotion.  
Music should support the scene.  
SFX should support the environment.  
Captions should support comprehension.  
Editing should connect everything into one coherent devotional experience.
