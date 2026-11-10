import os
import datetime
import time
from tavily import TavilyClient
from google import genai
from google.genai import types

# ==========================================
# 1. API Clients initialiseren
# ==========================================
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

today = datetime.date.today().isoformat()
audio_filename = f"episode_{today}.mp3"

# ==========================================
# 2. Live AI Web-research via Tavily
# ==========================================
print("1. Live web-research uitvoeren via Tavily...")
search_result = tavily_client.search(
    query="most fascinating scientific breakthroughs discoveries technology news last 24 hours",
    search_depth="advanced",
    max_results=5,
    include_answer=True
)

news_context = search_result.get("answer", "")
for res in search_result.get("results", []):
    news_context += f"\n\nSource: {res['title']}\n{res['content']}"

print("Onderzoek afgerond! Nieuws verzameld.")

# ==========================================
# 3. Dialoog schrijven met Gemini (met 503-retry)
# ==========================================
print("2. Dialoog schrijven met Gemini 3.8 Flash...")

prompt_script = f"""
Here is the latest breaking science & tech research collected live from the web:
{news_context}

Write a dynamic 5-minute podcast dialogue for 'Always Keep Learning' based on these discoveries.

Hosts:
- SOPHIE: Enthusiastic, genuinely curious host. Warm, relatable, keeps the pace lively, reacts naturally.
- MARK: Analytical, thoughtful expert. Uses everyday analogies, grounded, questions hype.

Rules:
- Natural, conversational spoken English (no newsreader tone).
- Keep speaking turns short (1 to 3 sentences per turn) for active banter.
- Use strictly these prebuilt voice tags for multi-speaker audio:
[Speaker: Aoede]
Sophie: (excited) Opening line...

[Speaker: Puck]
Mark: (thoughtful) Response...
"""

script_text = None
for attempt in range(1, 4):
    try:
        response_script = gemini_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt_script
        )
        script_text = response_script.text
        print("Script succesvol geschreven door Gemini 3.8 Flash!")
        break
    except Exception as e:
        if "503" in str(e) and attempt < 3:
            print(f"Piekdrukte bij Google (poging {attempt}/3). 10 seconden wachten...")
            time.sleep(10)
        else:
            print("Piekdrukte duurt langer; overschakelen naar gratis back-up gemini-3.5-flash-lite...")
            response_script = gemini_client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt_script
            )
            script_text = response_script.text
            print("Script succesvol geschreven via Gemini 3.5 Flash-Lite!")
            break

# ==========================================
# 4. Audio renderen via Gemini 3.8 Flash TTS
# ==========================================
print("3. Tweestemmige audio renderen via Gemini 3.8 Flash TTS...")

for attempt in range(1, 4):
    try:
        response_audio = gemini_client.models.generate_content(
            model='gemini-3.8-flash-tts',
            contents=script_text,
            config=types.GenerateContentConfig(
                response_mime_type="audio/mp3"
            ),
        )
        
        # Audiobestand opslaan
        audio_bytes = response_audio.candidates[0].content.parts[0].inline_data.data
        with open(audio_filename, "wb") as f:
            f.write(audio_bytes)
            
        print(f"Succes! Audiobestand opgeslagen als: {audio_filename}")
        break
    except Exception as e:
        if "503" in str(e) and attempt < 3:
            print(f"Piekdrukte op de audio-servers (poging {attempt}/3). 10 seconden wachten...")
            time.sleep(10)
        else:
            raise e
