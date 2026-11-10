import os
import datetime
from tavily import TavilyClient
from google import genai
from google.genai import types

# 1. Clients initialiseren
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

today = datetime.date.today().isoformat()
audio_filename = f"episode_{today}.mp3"

# 2. Live AI-websearch via Tavily
print("1. Live web-research uitvoeren via Tavily...")
search_result = tavily_client.search(
    query="most fascinating scientific breakthroughs discoveries technology news last 24 hours",
    search_depth="advanced",
    max_results=5,
    include_answer=True
)

# Tavily geeft een kant-en-klaar overzicht van het actuele nieuws
news_context = search_result.get("answer", "")
for res in search_result.get("results", []):
    news_context += f"\n\nSource: {res['title']}\n{res['content']}"

print("Onderzoek afgerond! Nieuws verzameld.")

# 3. Gemini het dialoog-script laten schrijven
print("2. Dialoog schrijven met Gemini 3.8 Flash...")
prompt_script = f"""
Here is the latest breaking science & tech research collected live from the web:
{news_context}

Write a 5-minute dynamic podcast dialogue for 'Always Keep Learning' based on these discoveries.
Hosts:
- SOPHIE: Enthusiastic, genuinely curious host. Warm, relatable, asks great questions.
- MARK: Analytical, thoughtful expert. Uses everyday analogies, grounded, questions hype.

Use strictly these voice tags for multi-speaker audio:
[Speaker: Aoede]
Sophie: (excited) Opening line...

[Speaker: Puck]
Mark: (thoughtful) Response...
"""

response_script = gemini_client.models.generate_content(
    model='gemini-3.8-flash',
    contents=prompt_script
)
script_text = response_script.text
print("Script succesvol geschreven!")

# 4. Tweestemmige audio renderen via Gemini 3.8 Flash TTS
print("3. Audio genereren via Gemini 3.8 Flash TTS...")
response_audio = gemini_client.models.generate_content(
    model='gemini-3.8-flash-tts',
    contents=script_text,
    config=types.GenerateContentConfig(
        response_mime_type="audio/mp3"
    ),
)

with open(audio_filename, "wb") as f:
    f.write(response_audio.candidates[0].content.parts[0].inline_data.data)

print(f"Geweldig! Audio succesvol opgeslagen als {audio_filename}")
