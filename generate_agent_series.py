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
            res = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return res.text
        except Exception as e:
            if "503" in str(e):
                print(f"Model {model_name} busy. Retrying next...")
                time.sleep(2)
            else:
                print(f"Error with {model_name}: {e}")
    raise RuntimeError("All text models busy.")

# 4. Schrijf 3 acts als gestructureerde JSON
act_titles = [
    "Act 1: The Recap, Architectural Motivation, and the Core Problem",
    "Act 2: Technical Deep Dive - Mechanisms, Protocols, and Data Structures",
    "Act 3: Practical Implementation, Edge Cases, and Today's Builder Challenge"
]

all_dialogue_turns = []

for act_num, act_title in enumerate(act_titles, 1):
    print(f"Scripting {act_title} (JSON)...")
    act_prompt = f"""
You are writing a script for a technical masterclass podcast called 'Building Your Sovereign AI Assistant'.
Episode {ep_number}: {ep_title} (Phase: {ep_phase}).

CONTEXT FROM PREVIOUS LESSONS:
{previous_summary}

TODAY'S CORE SUBJECT:
{core_concept}
PRACTICAL HOMEWORK:
{homework}

CURRENT SECTION: {act_title}

HOST PERSONAS:
- SOPHIE: Lead Developer. Passionate, pragmatic, asks probing questions about architecture and trade-offs.
- MARK: Lead AI Systems Architect. Calm, rigorous, seasoned systems engineer.

PACING & AUDIO RULES:
1. Write deep, highly technical dialogue with short turns (1-3 sentences per turn).
2. Insert <short pause> after complex points and for breathing space.
3. Use natural tags like <breath> or <laugh>.
4. Total length for this act: ~20 to 24 alternating turns.

OUTPUT FORMAT:
Strictly output a valid JSON array of objects with 'speaker' ('Sophie' or 'Mark') and 'text':
[
  {{"speaker": "Sophie", "text": "Morning Mark! <short pause> Today we tackle the core architecture."}},
  {{"speaker": "Mark", "text": "That's right Sophie. <breath> Let's look at how agents differ from passive models."}}
]
"""
    raw_json = call_gemini(act_prompt).strip()
    if raw_json.startswith("```"):
        raw_json = raw_json.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    
    turns = json.loads(raw_json)
    all_dialogue_turns.extend(turns)
    time.sleep(2)

print(f"Total dialogue turns scripted: {len(all_dialogue_turns)}")

# 5. Audio renderen in veilige Micro-Batches van 6 beurten (voorkomt voice-swap!)
speech_config = types.SpeechConfig(
    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=[
            types.SpeakerVoiceConfig(speaker="Sophie", voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede"))),
            types.SpeakerVoiceConfig(speaker="Mark", voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")))
        ]
    )
)

BATCH_SIZE = 6  # 3 beurten per spreker: perfecte conversatie zonder drift
all_wav_chunks = []

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

turn_batches = list(chunk_list(all_dialogue_turns, BATCH_SIZE))
print(f"Rendering {len(turn_batches)} conversational audio blocks...")

for b_idx, batch in enumerate(turn_batches, 1):
    dialogue_parts = []
    for turn in batch:
        spk = "Sophie" if turn["speaker"].strip().lower() == "sophie" else "Mark"
        txt = turn["text"].strip()
        if txt:
            dialogue_parts.append(
                types.Part(text=txt, speech_metadata=types.SpeechMetadata(speaker=spk))
            )
            
    tts_contents = [types.Content(role="user", parts=dialogue_parts)]
    
    for attempt in range(1, 4):
        try:
            res_audio = gemini_client.models.generate_content(
                model='gemini-3.8-flash-tts',
                contents=tts_contents,
                config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=speech_config)
            )
            all_wav_chunks.append(res_audio.candidates[0].content.parts[0].inline_data.data)
            print(f"Block {b_idx}/{len(turn_batches)} rendered successfully.")
            time.sleep(2)
            break
        except Exception as e:
            if "503" in str(e) and attempt < 3:
                print(f"Server busy on block {b_idx}. Waiting 10s...")
                time.sleep(10)
            else:
                raise e

# 6. Alle audioblokjes naadloos monteren tot 1 aflevering
print("Stitching all audio blocks into master episode...")
infiles = [io.BytesIO(b) for b in all_wav_chunks]
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

# 7. Samenvatting maken en state updaten
summary_prompt = f"""Summarize Episode {ep_number}: '{ep_title}' in 3 concise sentences so the hosts can recap it naturally tomorrow morning."""
today_summary = call_gemini(summary_prompt).strip()

state["current_episode_index"] = current_idx + 1
state["previous_episode_summary"] = f"In Episode {ep_number} ({ep_title}), we explored: {today_summary}"

with open("state_agent.json", "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2)

# 8. RSS Feed (feed_agent.xml) bijwerken
repo_full = os.environ.get("GITHUB_REPOSITORY", "jouw-naam/keep-learning")
owner, repo_name = repo_full.split("/")
base_url = f"https://{owner}.github.io/{repo_name}"
audio_url = f"{base_url}/{audio_filename}"
pub_date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

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
    feed_content = existing.replace("<channel>", f"<channel>\n{new_item}")

with open(feed_file, "w", encoding="utf-8") as f:
    f.write(feed_content)

print(f"feed_agent.xml successfully updated with Episode {ep_number}!")
