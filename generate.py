import os
import json
import datetime
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
today = datetime.date.today().isoformat()
audio_filename = f"episode_{today}.mp3"

print("1. Nieuws zoeken en dialoog schrijven met Gemini 3.8 Flash...")
prompt_script = """
Search the web for the top 2 to 3 most fascinating scientific breakthroughs, tech discoveries, or nature insights from the LAST 24 HOURS.
Write a 5-minute dynamic podcast dialogue for 'Always Keep Learning' between two hosts.

Use strictly Google's prebuilt voices:
- Sophie uses [Speaker: Aoede] (enthusiastic, curious, natural)
- Mark uses [Speaker: Puck] (calm, analytical, grounded expert)

Format:
[Speaker: Aoede]
Sophie: (excited) Opening line...

[Speaker: Puck]
Mark: (thoughtful) Response...
"""

response_script = client.models.generate_content(
    model='gemini-3.8-flash',
    contents=prompt_script,
    config=types.GenerateContentConfig(
        tools=[{"google_search": {}}]
    ),
)
script_text = response_script.text

print("2. Tweestemmige audio renderen via Gemini 3.8 Flash TTS...")
response_audio = client.models.generate_content(
    model='gemini-3.8-flash-tts',
    contents=script_text,
    config=types.GenerateContentConfig(
        response_mime_type="audio/mp3"
    ),
)

# Sla het MP3-bestand op
with open(audio_filename, "wb") as f:
    f.write(response_audio.candidates[0].content.parts[0].inline_data.data)

print(f"Audio succesvol opgeslagen als {audio_filename}")
