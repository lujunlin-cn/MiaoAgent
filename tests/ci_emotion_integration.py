#!/usr/bin/env python3
import wave
import os
import sys
import contextlib

# Ensure project root is on sys.path so `skills` can be imported when running tests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from skills.shared.event_store import store

# Create a short 1-second silent WAV at 16kHz
OUT = '/tmp/catagent_test_silence.wav'
RATE = 16000
DUR = 1.0
NUM_SAMPLES = int(RATE * DUR)

if not os.path.exists(OUT):
    import struct
    with wave.open(OUT, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        silent = (b"\x00\x00" * NUM_SAMPLES)
        wf.writeframes(silent)

print('Test WAV:', OUT)

# Clear event store
store.clear_all()

# Import detectors lazily and run
try:
    from skills.emotion_perception.voice_emotion import analyze_voice_emotion
except Exception as e:
    print('Failed to import voice_emotion:', e)
    analyze_voice_emotion = None

try:
    from skills.emotion_perception.env_audio import analyze_env_audio
except Exception as e:
    print('Failed to import env_audio:', e)
    analyze_env_audio = None

if analyze_voice_emotion:
    try:
        r = analyze_voice_emotion(OUT)
        print('voice_emotion result:', r)
    except Exception as e:
        print('voice_emotion run error:', e)

if analyze_env_audio:
    try:
        r = analyze_env_audio(OUT)
        print('env_audio result:', r)
    except Exception as e:
        print('env_audio run error:', e)

print('\nEventStore stats:')
print(store.stats())

# Show recent events
recent = store.get_recent(minutes=10)
print('\nRecent events:')
for ev in recent:
    print(ev.to_evidence_line())

print('\nDone')
