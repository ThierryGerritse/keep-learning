import os
import json
import datetime
import time
import io
import wave
from google import genai
from google.genai import types

# 1. Clients initialiseren
gemini_client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={'api_version': 'v1beta'}
)

# 2. State & Curriculum laden
with open("state_agent.json", "r", encoding="utf-8") as f:
    state = json.load(f)

with open("curriculum.json", "r", encoding="utf-8") as f:
    curriculum = json.load(f)

current_idx = state.get("current_episode_index", 0)
if current_idx >= len(curriculum):
    print("Gefeliciteerd! De complete 35-delige serie is afgerond.")
    exit(0)

ep_data = curriculum[current_idx]
ep_number = ep_data["episode"]
ep_title = ep_data["title"]
ep_phase = ep_data["phase"]
core_concept = ep_data["core_concept"]
homework = ep_data["homework"]
previous_summary = state.get("previous_episode_summary", "This is the series premiere.")

print(f"--- GENERATING EPISODE {ep_number}: {ep_title} ---")
today = datetime.date.today().isoformat()
audio_filename = f"agent_ep_{ep_number:02d}_{today}.wav"

# 3. Model fallback waterval
CANDIDATE_MODELS = ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']

def call_gemini(prompt):
    for model_name in CANDIDATE_MODELS:
        try:
            res = gemini_client.models.generate_content(model=model_name, contents=prompt)
            return res.text
        except Exception as e:
            if "503" in str(e):
                print(f"Model {model_name} busy. Retrying next...")
                time.sleep(2)
            else:
                print(f"Error with {model_name}: {e}")
    raise RuntimeError("All text models busy.")

# 4. Schrijf 3 opeenvolgende acts voor een totale lengte van ~18 minuten
acts = []
act_titles = [
    "Act 1: The Recap, Architectural Motivation, and the Core Problem",
    "Act 2: Technical Deep Dive - Mechanisms, Protocols, and Data Structures",
    "Act 3: Practical Implementation, Edge Cases, and Today's Builder Challenge"
]

conversation_history_for_next_act = ""

for act_num, act_title in enumerate(act_titles, 1):
    print(f"Generating {act_title}...")
    act_prompt = f"""
You are writing a script for a 15-20 minute engineering masterclass podcast called 'Building Your Sovereign AI Assistant'.
Episode {ep_number}: {ep_title} (Phase: {ep_phase}).

CONTEXT FROM PREVIOUS LESSONS:
{previous_summary}

TODAY'S CORE SUBJECT:
{core_concept}
PRACTICAL HOMEWORK FOR THE BUILDER:
{homework}

CURRENT SECTION TO WRITE: {act_title}
(Previous context in this episode: {conversation_history_for_next_act if conversation_history_for_next_act else 'Starting the episode.'})

HOST PERSONAS:
- SOPHIE: Lead Developer. Passionate, pragmatic, writes the code, hits practical roadblocks, asks about performance and trade-offs.
- MARK: Lead AI Systems Architect. Calm, rigorous, seasoned systems thinker, explains engineering patterns and edge cases.

PACING & AUDIO RULES:
1. Write deep, highly technical, intellectual dialogue (NOT superficial hype).
2. Insert <short pause> after complex explanations, between thoughts, and for natural breathing.
3. Use <breath> and <laugh> where appropriate.
4. Target length for this act: ~750-800 words of spoken dialogue.
5. Format EVERY line strictly as:
Sophie: Spoken text here with <short pause> breathing room.
Mark: Calm answer here <breath> explaining the architecture.
"""
    act_text = call_gemini(act_prompt)
    acts.append(act_text)
    conversation_history_for_next_act += f"\n[Summary of Act {act_num} generated]\n"
    time.sleep(2)

print("All 3 acts scripted successfully. Total length: ~2,300 words.")

# 5. Audio renderen per act en samenvoegen
speech_config = types.SpeechConfig(
    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=[
            types.SpeakerVoiceConfig(speaker="Sophie", voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede"))),
            types.SpeakerVoiceConfig(speaker="Mark", voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")))
        ]
    )
)

act_wav_bytes = []

for idx, act_text in enumerate(acts, 1):
    print(f"Rendering Act {idx}/3 audio via Gemini 3.8 Flash TTS...")
    dialogue_parts = []
    for line in act_text.strip().split("\n"):
        clean = line.strip().replace("**", "")
        if clean.lower().startswith("sophie:"):
            txt = clean.split(":", 1)[1].strip()
            if txt:
                dialogue_parts.append(types.Part(text=txt, speech_metadata=types.SpeechMetadata(speaker="Sophie")))
        elif clean.lower().startswith("mark:"):
            txt = clean.split(":", 1)[1].strip()
            if txt:
                dialogue_parts.append(types.Part(text=txt, speech_metadata=types.SpeechMetadata(speaker="Mark")))
                
    tts_contents = [types.Content(role="user", parts=dialogue_parts)]
    
    for attempt in range(1, 4):
        try:
            res_audio = gemini_client.models.generate_content(
                model='gemini-3.8-flash-tts',
                contents=tts_contents,
                config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=speech_config)
            )
            act_wav_bytes.append(res_audio.candidates[0].content.parts[0].inline_data.data)
            print(f"Act {idx} audio generated.")
            time.sleep(3)
            break
        except Exception as e:
            if "503" in str(e) and attempt < 3:
                print(f"Audio server busy (attempt {attempt}/3). Waiting 10s...")
                time.sleep(10)
            else:
                raise e

# 6. Audio naadloos samenvoegen tot 1 lange aflevering
print("Stitching acts into full 15-20 min master episode...")
infiles = [io.BytesIO(b) for b in act_wav_bytes]
with wave.open(infiles[0], 'rb') as w_first:
    params = w_first.getparams()
    frames = [w_first.readframes(w_first.getnframes())]

for f in infiles[1:]:
    with wave.open(f, 'rb') as w:
        frames.append(w.readframes(w.getnframes()))

with wave.open(audio_filename, 'wb') as w_out:
    w_out.setparams(params)
    for fr in frames:
        w_out.writeframes(fr)

file_size = os.path.getsize(audio_filename)
print(f"MASTER EPISODE COMPLETED: {audio_filename} ({file_size / (1024*1024):.2f} MB)")

# 7. Genereer een samenvatting van vandaag voor de recap van morgen
summary_prompt = f"""Summarize Episode {ep_number}: '{ep_title}' in 3 concise sentences so the hosts can recap it naturally tomorrow morning."""
today_summary = call_gemini(summary_prompt).strip()

# Update state.json
state["current_episode_index"] = current_idx + 1
state["previous_episode_summary"] = f"In Episode {ep_number} ({ep_title}), we explored: {today_summary}"

with open("state_agent.json", "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2)

print(f"State updated: Next episode will be #{current_idx + 2}")

# 8. RSS Feed (feed_agent.xml) bijwerken
print("Updating feed_agent.xml for Apple Podcasts...")
repo_full = os.environ.get("GITHUB_REPOSITORY", "jouw-naam/keep-learning")
owner, repo_name = repo_full.split("/")
base_url = f"https://{owner}.github.io/{repo_name}"
audio_url = f"{base_url}/{audio_filename}"
pub_date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

# Nieuw item voor de feed
new_item = f"""    <item>
      <title>Episode {ep_number:02d}: {ep_title}</title>
      <description>{core_concept} Homework: {homework}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{audio_url}" type="audio/wav" length="{file_size}" />
      <guid>{audio_url}</guid>
    </item>"""

feed_file = "feed_agent.xml"
if not os.path.exists(feed_file):
    feed_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Building Your Sovereign AI Assistant</title>
    <link>{base_url}</link>
    <language>en-us</language>
    <itunes:author>Sophie &amp; Mark</itunes:author>
    <description>A 35-part serialized engineering masterclass on designing, coding, and deploying an autonomous personal AI agent from scratch.</description>
{new_item}
  </channel>
</rss>
"""
else:
    with open(feed_file, "r", encoding="utf-8") as f:
        existing = f.read()
    # Voeg het nieuwe item bovenaan in het channel toe
    feed_content = existing.replace("<channel>", f"<channel>\n{new_item}")

with open(feed_file, "w", encoding="utf-8") as f:
    f.write(feed_content)

print(f"feed_agent.xml successfully updated with Episode {ep_number}!")
