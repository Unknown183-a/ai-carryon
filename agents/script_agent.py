# agents/script_agent.py
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")

def create_script(research_data):
    prompt = f"""
    Write a YouTube Shorts script based on this research.
    Target duration: 45-60 seconds when spoken aloud.
    Target word count: 200-250 words.

    Rules:
    - Sound like a real human talking, NOT a robot
    - Use natural conversational language: "So basically...", "Here's the thing...", "Right?", "And honestly...", "Wait, actually..."
    - Short punchy sentences. Max 12 words per sentence.
    - Start with a shocking/curiosity hook in the first 3 seconds
    - Build up with 3-4 interesting facts or points about the topic
    - Use transitions like "But here's the crazy part...", "And it gets better...", "So what does this mean?"
    - End with a quick CTA like "Follow for more wild tech facts"
    - NO labels like "Hook:", "CTA:", no timestamps, no quotes
    - Write ONLY the spoken words, nothing else
    - NO bullet points, just flowing natural speech

    Research: {research_data}

    Example style (notice the length and flow):
    So this tiny chip inside your phone? It has more transistors than there are stars in the Milky Way. Seriously. We're talking about 15 billion transistors on something smaller than your fingernail. That's kind of insane, right? But here's the crazy part. Each transistor is only 3 nanometers wide. To put that in perspective, a strand of your hair is about 80,000 nanometers wide. So we're fitting billions of these things in a space you literally cannot see. And it gets better. These transistors switch on and off billions of times every single second. That's what makes your phone fast. That's what lets you stream, game, and scroll — all at the same time. Now the wild thing is, we're almost at the physical limit. We can't make them much smaller because quantum physics starts doing weird stuff. Electrons just start teleporting through walls. I'm not even joking. So what happens next? Companies like Apple and TSMC are stacking chips in 3D now. Going vertical instead of smaller. The future of computing is literally going upward. Follow for more wild tech facts that nobody talks about.
    """

    response = llm.invoke(prompt).content
    return response.strip()
