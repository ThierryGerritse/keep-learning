import os
import datetime
import time
from tavily import TavilyClient
from google import genai
from google.genai import types

# ==========================================
# 1. API Clients initialiseren
# ==========================================
gemini_client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={'api_version': 'v1beta'}
)
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

today = datetime.date.today().isoformat()
timestamp = datetime.datetime.now().strftime("%H%M")
audio_filename = f"episode_{today}_{timestamp}.wav"

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
# 3. Dialoog schrijven met Gemini (Pacing & Regie)
# ==========================================
print("2. Dialoog schrijven met Gemini...")

prompt_script = f"""
Here is the latest breaking science & tech research collected live from the web:
{news_context}

Write a relaxed, easy-to-follow 5-minute podcast episode for 'Always Keep Learning'.

Hosts:
- SOPHIE: Enthusiastic, genuinely curious host. Warm, relatable, keeps the pace clear.
- MARK: Analytical, thoughtful expert. Calm, grounded, speaks with measured wisdom.

IMPORTANT AUDIO & PACING RULES:
1. Do NOT rush. Write with an unhurried, relaxed cadence so listeners can absorb the ideas.
2. Use <short pause> after key facts, between thoughts, and at the end of sentences to create breathing room.
3. Use audio tags like <laugh>, <breath>, or <sigh> naturally.
4. Do NOT use brackets like [Speaker: ...] and do NOT write stage directions in parentheses like (excited).
5. Format EVERY line strictly as:
Sophie: Spoken text here with <short pause> natural breathing room.
Mark: Calm answer here <breath> explaining the idea simply.
"""

CANDIDATE_MODELS = [
    'gemini-3.8-flash',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite'
]

script_text = None
for model_name in CANDIDATE_MODELS:
    try:
        print(f"Poging om dialoog te schrijven met {model_name}...")
        response_script = gemini_client.models.generate_content(
            model=model_name,
            contents=prompt_script
        )
        script_text = response_script.text
        print(f"Script succesvol geschreven door {model_name}!")
        break
    except Exception as e:
        if "503" in str(e):
            print(f"Model {model_name} ervaart piekdrukte (503). We schakelen door...")
            time.sleep(2)
        else:
            print(f"Fout bij {model_name}: {e}")

if not script_text:
    raise RuntimeError("Alle tekstmodellen waren tijdelijk overbelast.")

# ==========================================
# 4. Tweestemmige audio via Gemini 3.8 Flash TTS
# ==========================================
print("3. Tweestemmige audio renderen via Gemini 3.8 Flash TTS...")

# Officiële multi-speaker koppeling: Sophie -> Aoede, Mark -> Puck
speech_config = types.SpeechConfig(
    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=[
            types.SpeakerVoiceConfig(
                speaker="Sophie",
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            types.SpeakerVoiceConfig(
                speaker="Mark",
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                )
            )
        ]
    )
)

audio_bytes = None
for attempt in range(1, 4):
    try:
        response_audio = gemini_client.models.generate_content(
            model='gemini-3.8-flash-tts',
            contents=script_text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config
            ),
        )
        
        part = response_audio.candidates[0].content.parts[0]
        audio_bytes = part.inline_data.data
        
        with open(audio_filename, "wb") as f:
            f.write(audio_bytes)
            
        print(f"GEWELDIG! Audiobestand succesvol opgeslagen als: {audio_filename}")
        break

    except Exception as e:
        if "503" in str(e) and attempt < 3:
            print(f"Piekdrukte op de audio-servers (poging {attempt}/3). 10 seconden wachten...")
            time.sleep(10)
        else:
            print(f"Fout bij audio-generatie: {e}")
            raise e

# ==========================================
# 5. Podcast RSS-feed (feed.xml) bijwerken
# ==========================================
print("4. Podcast RSS-feed bijwerken voor Apple Podcasts...")

repo_full = os.environ.get("GITHUB_REPOSITORY", "jouw-naam/keep-learning")
owner, repo_name = repo_full.split("/")

base_url = f"https://{owner}.github.io/{repo_name}"
audio_url = f"{base_url}/{audio_filename}"
file_size = len(audio_bytes) if audio_bytes else 10000000
pub_date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

feed_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Altijd Blijven Leren</title>
    <link>{base_url}</link>
    <language>en-us</language>
    <itunes:author>Sophie &amp; Mark</itunes:author>
    <description>Daily 5-minute science and tech breakthrough podcast hosted by Sophie and Mark.</description>
    <item>
      <title>Always Keep Learning - {today}</title>
      <description>Daily science briefing with Sophie and Mark.</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{audio_url}" type="audio/wav" length="{file_size}" />
      <guid>{audio_url}</guid>
    </item>
  </channel>
</rss>
"""

with open("feed.xml", "w", encoding="utf-8") as f:
    f.write(feed_content)

print("Feed.xml succesvol klaargezet voor Apple Podcasts!")
