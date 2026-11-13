#!/usr/bin/env python3
"""ElevenLabs TTS helper for animation voiceovers (stdlib only).

Usage:
  # Single line of text
  python3 tts/elevenlabs_tts.py say "Merhaba dünya" -o out/merhaba.mp3

  # A whole animation script (JSON), one audio file per scene + timings
  python3 tts/elevenlabs_tts.py script tts/example_script.json -o out/

Each generated .mp3 gets a sibling .json with character/word timings and the
total duration, so animations can be synced to the voice.

API key: read from ELEVENLABS_API_KEY. In the Claude cloud environment the
network proxy injects the real key into requests to api.elevenlabs.io, so the
variable may be unset (a placeholder is sent and replaced by the proxy).
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "George" - premade, multilingual
DEFAULT_MODEL = "eleven_multilingual_v2"  # supports Turkish
DEFAULT_FORMAT = "mp3_44100_128"


def tts(text, voice_id=DEFAULT_VOICE, model_id=DEFAULT_MODEL,
        output_format=DEFAULT_FORMAT, voice_settings=None, language_code=None):
    """Return (audio_bytes, alignment_dict) for the given text."""
    body = {"text": text, "model_id": model_id}
    if voice_settings:
        body["voice_settings"] = voice_settings
    if language_code:
        body["language_code"] = language_code
    url = f"{API}/text-to-speech/{voice_id}/with-timestamps?output_format={output_format}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "proxy-injected"),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs error {e.code}: {e.read().decode(errors='replace')}")
    return base64.b64decode(data["audio_base64"]), data.get("alignment") or {}


def words_from_alignment(al):
    """Group character timings into word timings."""
    chars = al.get("characters", [])
    starts = al.get("character_start_times_seconds", [])
    ends = al.get("character_end_times_seconds", [])
    words, cur, s, e = [], "", None, None
    for c, cs, ce in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                words.append({"word": cur, "start": s, "end": e})
            cur, s = "", None
            continue
        if s is None:
            s = cs
        cur += c
        e = ce
    if cur:
        words.append({"word": cur, "start": s, "end": e})
    return words


def synth_to_file(text, out_path, **kw):
    audio, al = tts(text, **kw)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(audio)
    words = words_from_alignment(al)
    ends = al.get("character_end_times_seconds") or [0]
    meta = {"text": text, "audio": os.path.basename(out_path),
            "duration": ends[-1], "words": words, "alignment": al}
    with open(os.path.splitext(out_path)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"{out_path}  ({meta['duration']:.2f}s, {len(words)} words)")
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("say", help="synthesize one text")
    s.add_argument("text")
    s.add_argument("-o", "--out", default="out/tts.mp3")

    sc = sub.add_parser("script", help="synthesize every scene in a JSON script")
    sc.add_argument("file")
    sc.add_argument("-o", "--out", default="out")

    for sp in (s, sc):
        sp.add_argument("--voice", default=None)
        sp.add_argument("--model", default=None)
        sp.add_argument("--format", default=None)
    a = p.parse_args()

    if a.cmd == "say":
        synth_to_file(a.text, a.out, voice_id=a.voice or DEFAULT_VOICE,
                      model_id=a.model or DEFAULT_MODEL,
                      output_format=a.format or DEFAULT_FORMAT)
        return

    with open(a.file, encoding="utf-8") as f:
        script = json.load(f)
    voice = a.voice or script.get("voice", DEFAULT_VOICE)
    model = a.model or script.get("model", DEFAULT_MODEL)
    fmt = a.format or script.get("format", DEFAULT_FORMAT)
    manifest = []
    for i, scene in enumerate(script["scenes"], 1):
        sid = scene.get("id", f"scene{i:02d}")
        meta = synth_to_file(
            scene["text"], os.path.join(a.out, f"{sid}.mp3"),
            voice_id=scene.get("voice", voice), model_id=model, output_format=fmt,
            voice_settings=scene.get("voice_settings", script.get("voice_settings")),
            language_code=scene.get("language_code", script.get("language_code")),
        )
        manifest.append({"id": sid, "audio": meta["audio"], "duration": meta["duration"],
                         "text": scene["text"]})
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"manifest: {os.path.join(a.out, 'manifest.json')}")


if __name__ == "__main__":
    main()
