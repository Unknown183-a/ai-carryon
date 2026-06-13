import os
import requests
from dotenv import load_dotenv
load_dotenv()


def fetch_trending_topics(region_code="US", max_results=25):
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet",
        "chart": "mostPopular",
        "regionCode": region_code,
        "maxResults": max_results,
        "videoCategoryId": "28",
        "key": YOUTUBE_API_KEY
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    titles = [item["snippet"]["title"] for item in data.get("items", [])]
    return titles


def pick_best_topic(trending_titles):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(trending_titles)])

    prompt = f"""
    Below are currently trending YouTube video titles in the last 24 hours.

    {titles_text}

    Your job:
    1. Identify the most viral, interesting tech/AI/science topic from this list
    2. Rephrase it as a clear, specific YouTube Shorts topic (under 10 words)
    3. It should be something that can be explained in 30-50 seconds

    Return ONLY the topic phrase, nothing else. No numbering, no explanation.

    Example output: "How Claude AI beats ChatGPT in coding"
    """

    response = llm.invoke(prompt).content.strip()
    return response.strip('"').strip("'")


def get_trending_topic(region_code="US"):
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY not set in .env file")

    print("Fetching trending YouTube topics...")
    trending_titles = fetch_trending_topics(region_code=region_code)

    if not trending_titles:
        raise ValueError("No trending topics found")

    print(f"Found {len(trending_titles)} trending videos")
    topic = pick_best_topic(trending_titles)
    print(f"Selected topic: {topic}")
    return topic