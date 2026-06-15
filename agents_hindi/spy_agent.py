# agents_hindi/spy_agent.py
import os
import json
import time
import re
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")

def get_hindi_trending_topics():
    CACHE_FILE = "output/spy_cache_hindi.json"

    # Cache valid for 2 hours
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < 7200:
            print("Using cached Hindi trending topics")
            return cache["topics"]

    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    # Use Groq with web search to find trending Hindi tech Shorts
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": """Search the web and find the TOP 10 trending Hindi tech YouTube Shorts 
                from the last 24 hours. 

                Look for:
                - Hindi tech YouTube Shorts that went viral today
                - Indian tech channels posting trending Shorts
                - Topics like AI, smartphones, gadgets, apps in Hindi

                For each video return:
                1. Channel name
                2. Video title
                3. Topic (in English, 5-8 words)
                4. Why it's trending
                5. Suggested tags (10 Hindi+English tags)
                6. Suggested description (50 words in Hindi)

                Return as JSON array:
                [
                  {
                    "channel": "channel name",
                    "title": "original video title",
                    "topic": "topic in english",
                    "why_trending": "reason",
                    "tags": ["tag1", "tag2"],
                    "description": "hindi description",
                    "views": 50000,
                    "url": "youtube url if known"
                  }
                ]
                Return ONLY the JSON array, nothing else."""
            }
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        }
                    },
                    "required": ["query"]
                }
            }
        }],
        tool_choice="auto",
        temperature=0.3
    )

    # Get the response content
    content = response.choices[0].message.content or ""
    
    # Clean JSON
    content = content.strip()
    content = re.sub(r'^```json\n?', '', content)
    content = re.sub(r'^```\n?', '', content)
    content = re.sub(r'\n?```$', '', content)

    try:
        topics = json.loads(content)
        if not isinstance(topics, list):
            topics = []
    except:
        # If JSON fails, use Groq without tools to generate trending topics
        topics = []

    # If web search didn't work, use Groq knowledge
    if not topics:
        print("Web search failed, using Groq knowledge...")
        response2 = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": """Based on your knowledge, what are the TOP 10 most trending 
                    Hindi tech topics RIGHT NOW in India for YouTube Shorts?
                    
                    Think about:
                    - Latest smartphone launches in India
                    - AI tools Indians are using
                    - Latest apps trending in India
                    - Tech news from last few days in India
                    - Viral tech facts in Hindi
                    
                    Return as JSON array:
                    [
                      {
                        "channel": "suggested channel type",
                        "title": "catchy hindi title for this topic",
                        "topic": "topic in english",
                        "why_trending": "reason its trending in India",
                        "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
                        "description": "50 word hindi description for youtube",
                        "views": 100000,
                        "url": "https://youtube.com"
                      }
                    ]
                    Return ONLY valid JSON array, nothing else."""
                }
            ],
            temperature=0.5
        )
        
        content2 = response2.choices[0].message.content or ""
        content2 = content2.strip()
        content2 = re.sub(r'^```json\n?', '', content2)
        content2 = re.sub(r'^```\n?', '', content2)
        content2 = re.sub(r'\n?```$', '', content2)
        
        try:
            topics = json.loads(content2)
            if not isinstance(topics, list):
                topics = []
        except:
            topics = []

    # Normalize format
    result = []
    for t in topics:
        result.append({
            'channel': t.get('channel', 'Hindi Tech'),
            'title': t.get('title', t.get('topic', '')),
            'topic': t.get('topic', ''),
            'why_trending': t.get('why_trending', ''),
            'tags': t.get('tags', ['hindi', 'tech', 'shorts', 'viral', 'india']),
            'description': t.get('description', ''),
            'views': t.get('views', 0),
            'likes': t.get('likes', 0),
            'published': t.get('published', 'Today'),
            'url': t.get('url', 'https://youtube.com'),
        })

    print(f"Found {len(result)} Hindi trending topics via Groq")

    # Save cache
    os.makedirs("output", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "topics": result}, f)

    return result


def get_best_hindi_topic():
    """Get single best trending Hindi topic for scheduler"""
    topics = get_hindi_trending_topics()
    if topics:
        best = topics[0]
        print(f"Best Hindi topic: {best['topic']}")
        return best
    return None
