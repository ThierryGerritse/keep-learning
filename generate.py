import os
import datetime
import time
from tavily import TavilyClient
from google import genai
from google.genai import types

# ==========================================
# 1. API Clients initialiseren (v1beta)
# ==========================================
gemini_client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={'api_version': 'v1beta'}
)
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

today = datetime.date.today().isoformat()
timestamp = datetime.datetime.now().strftime("%H%M")

audio_fn_en = f"episode_en_{today}_{timestamp}.wav"
audio_fn_nl = f"episode_nl_{today}_{timestamp}.wav"

# ==========================================
# 2. Live AI Web-research via Tavily (1x voor beide!)
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
# Hulpfuncties voor generatie
# ==========================================
CANDIDATE_MODELS = ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']

def generate_script(prompt, lang_name):
    print(f"2. Dialoog schrijven ({lang_name})...")
    for model_name in CANDIDATE_MODELS:
        try:
            res = gemini_client.models.generate_content(model=model_name, contents=prompt)
            print(f"Script ({lang_name}) succesvol geschreven door {model_name}!")
            return res.text
        except Exception as e:
            if "503" in str(e):
                print(f"Model {model_name} bezet (503). Volgende proberen...")
                time.sleep(2)
            else:
                print(f"Fout bij {model_name}: {e}")
    raise RuntimeError(f"Kon geen script genereren voor {lang_name}")

def render_audio(script_text, output_filename, lang_name):
    print(f"3. Audio renderen ({lang_name}) via Gemini 3.8 Flash TTS...")
    
    # Dialogue parts klaarmaken
    dialogue_parts = []
    for line in script_text.strip().split("\n"):
        clean_line = line.strip().replace("**", "")
        if not clean_line:
            continue
        if clean_line.lower().startswith("sophie:"):
            txt = clean_line.split(":", 1)[1].strip()
            if txt:
                dialogue_parts.append(types.Part(text=txt, speech_metadata=types.SpeechMetadata(speaker="Sophie")))
        elif clean_line.lower().startswith("mark:"):
            txt = clean_line.split(":", 1)[1].strip()
            if txt:
                dialogue_parts.append(types.Part(text=txt, speech_metadata=types.SpeechMetadata(speaker="Mark")))
                
    tts_contents = [types.Content(role="user", parts=dialogue_parts)]
    
    speech_config = types.SpeechConfig(
        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(speaker="Sophie", voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede"))),
                types.SpeakerVoiceConfig(speaker="Mark", voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")))
            ]
        )
    )
    
    for attempt in range(1, 4):
        try:
            res_audio = gemini_client.models.generate_content(
                model='gemini-3.8-flash-tts',
                contents=tts_contents,
                config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=speech_config)
            )
            audio_bytes = res_audio.candidates[0].content.parts[0].inline_data.data
            with open(output_filename, "wb") as f:
                f.write(audio_bytes)
            print(f"Audio ({lang_name}) succesvol opgeslagen als: {output_filename}")
            return audio_bytes
        except Exception as e:
            if "503" in str(e) and attempt < 3:
                print(f"Piekdrukte audio ({attempt}/3). 10s wachten...")
                time.sleep(10)
            else:
                raise e

# ==========================================
# 3. Engelse aflevering genereren
# ==========================================
prompt_en = f"""
Here is the latest breaking science & tech research:
{news_context}

Write a relaxed, easy-to-follow 5-minute podcast episode in ENGLISH for 'Always Keep Learning'.
Hosts:
- SOPHIE: Enthusiastic, genuinely curious host. Warm, relatable, keeps the pace clear.
- MARK: Analytical, thoughtful expert. Calm, grounded, speaks with measured wisdom.

RULES:
1. Write with an unhurried, measured cadence so listeners can comfortably follow along.
2. Insert <short pause> after key concepts and between thoughts.
3. Use vocal tags like <laugh>, <breath>, or <sigh> naturally.
4. Format EVERY line strictly as:
Sophie: Spoken words here with <short pause> breathing room.
Mark: Thoughtful answer here <breath> explaining the idea simply.
"""
script_en = generate_script(prompt_en, "Engels")
bytes_en = render_audio(script_en, audio_fn_en, "Engels")

# Korte pauze tussen beide calls om netjes binnen de limieten te blijven
time.sleep(5)

# ==========================================
# 4. Nederlandse aflevering genereren
# ==========================================
prompt_nl = f"""
Hier is het meest recente wetenschaps- en technologienieuws van vandaag:
{news_context}

Schrijf een ontspannen, natuurlijk podcast-gesprek van 5 minuten in het NEDERLANDS voor 'Altijd Blijven Leren'.
Presentatoren:
- SOPHIE: Enthousiaste, nieuwsgierige presentatrice. Warm, stelt goede vragen, houdt de vaart erin.
- MARK: Analytische, rustige expert. Legt complexe zaken eenvoudig uit met alledaagse voorbeelden.

REGELS:
1. Schrijf in vlot, natuurlijk gesproken Nederlands (geen stijve schrijftaal of journaal-toon).
2. Gebruik <short pause> na belangrijke feiten en tussen gedachten voor rust en ademruimte.
3. Gebruik <breath> en <laugh> waar dat natuurlijk aanvoelt.
4. Format ELKE regel strikt als:
Sophie: Gesproken tekst hier met <short pause> voldoende rust.
Mark: Rustig antwoord hier <breath> waarin het inzicht wordt uitgelegd.
"""
script_nl = generate_script(prompt_nl, "Nederlands")
bytes_nl = render_audio(script_nl, audio_fn_nl, "Nederlands")

# ==========================================
# 5. Podcast RSS-feed (feed.xml) bijwerken
# ==========================================
print("5. Podcast RSS-feed bijwerken met beide afleveringen...")

repo_full = os.environ.get("GITHUB_REPOSITORY", "jouw-naam/keep-learning")
owner, repo_name = repo_full.split("/")
base_url = f"https://{owner}.github.io/{repo_name}"

audio_url_en = f"{base_url}/{audio_fn_en}"
audio_url_nl = f"{base_url}/{audio_fn_nl}"
pub_date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

feed_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Altijd Blijven Leren</title>
    <link>{base_url}</link>
    <language>mul</language>
    <itunes:author>Sophie &amp; Mark</itunes:author>
    <description>Daily 5-minute science and tech breakthrough podcast in Dutch and English, hosted by Sophie and Mark.</description>
    <item>
      <title>🇳🇱 Altijd Blijven Leren - {today}</title>
      <description>Dagelijkse wetenschaps- en techupdate in het Nederlands met Sophie en Mark.</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{audio_url_nl}" type="audio/wav" length="{len(bytes_nl)}" />
      <guid>{audio_url_nl}</guid>
    </item>
    <item>
      <title>🇬🇧 Always Keep Learning - {today}</title>
      <description>Daily science and tech briefing in English with Sophie and Mark.</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{audio_url_en}" type="audio/wav" length="{len(bytes_en)}" />
      <guid>{audio_url_en}</guid>
    </item>
  </channel>
</rss>
"""

with open("feed.xml", "w", encoding="utf-8") as f:
    f.write(feed_content)

print("Feed.xml succesvol bijgewerkt met de NL en EN edities!")
