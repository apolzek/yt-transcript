import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "yt-transcript"


def load_module():
    loader = importlib.machinery.SourceFileLoader("yt_transcript", str(SCRIPT))
    spec = importlib.util.spec_from_loader("yt_transcript", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


yt = load_module()

SEGMENTS = [(0.0, 2.5, "Primeira frase."), (2.5, 3661.042, "Segunda frase.")]

# legenda manual simples
MANUAL_VTT = """WEBVTT
Kind: captions
Language: pt

00:00:01.000 --> 00:00:03.500
Olá, mundo.

00:00:03.500 --> 00:00:06.000
Segunda <i>linha</i>
continua aqui.
"""

# formato das legendas automáticas: cue settings na linha do tempo, tags de
# palavra e repetição da linha anterior (rolagem)
AUTO_VTT = """WEBVTT
Kind: captions
Language: pt

00:00:00.160 --> 00:00:02.000 align:start position:0%
um<00:00:00.500><c> teste</c><00:00:01.000><c> simples</c>

00:00:02.000 --> 00:00:02.010 align:start position:0%
um teste simples

00:00:02.010 --> 00:00:04.000 align:start position:0%
um teste simples
de<00:00:02.500><c> legenda</c>
"""


# ---------------------------------------------------------------- fmt_ts

@pytest.mark.parametrize("secs,sep,expected", [
    (0, ",", "00:00:00,000"),
    (1.5, ",", "00:00:01,500"),
    (61.25, ".", "00:01:01.250"),
    (3661.042, ",", "01:01:01,042"),
    (0.9996, ",", "00:00:01,000"),
])
def test_fmt_ts(secs, sep, expected):
    assert yt.fmt_ts(secs, sep) == expected


# ---------------------------------------------------------------- render

def test_render_txt():
    assert yt.render(SEGMENTS, "txt") == "Primeira frase.\nSegunda frase.\n"


def test_render_ts():
    assert yt.render(SEGMENTS, "ts") == "[00:00:00] Primeira frase.\n[00:00:02] Segunda frase.\n"


def test_render_srt():
    assert yt.render(SEGMENTS, "srt") == (
        "1\n00:00:00,000 --> 00:00:02,500\nPrimeira frase.\n\n"
        "2\n00:00:02,500 --> 01:01:01,042\nSegunda frase.\n"
    )


def test_render_vtt():
    out = yt.render(SEGMENTS, "vtt")
    assert out.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:02.500\nPrimeira frase." in out


def test_render_invalid_format():
    with pytest.raises(ValueError):
        yt.render(SEGMENTS, "docx")


# ---------------------------------------------------------------- parse_vtt

def test_parse_vtt_manual(tmp_path):
    f = tmp_path / "a.vtt"
    f.write_text(MANUAL_VTT, encoding="utf-8")
    assert yt.parse_vtt(f) == [
        (1.0, 3.5, "Olá, mundo."),
        (3.5, 6.0, "Segunda linha"),
        (3.5, 6.0, "continua aqui."),
    ]


def test_parse_vtt_auto_strips_tags_settings_and_duplicates(tmp_path):
    f = tmp_path / "a.vtt"
    f.write_text(AUTO_VTT, encoding="utf-8")
    texts = [t for _, _, t in yt.parse_vtt(f)]
    assert texts == ["um teste simples", "de legenda"]
    assert not any("align:" in t or "<" in t for t in texts)


def test_parse_vtt_short_timestamps(tmp_path):
    f = tmp_path / "a.vtt"
    f.write_text("WEBVTT\n\n01:02.500 --> 01:04.000\noi\n", encoding="utf-8")
    assert yt.parse_vtt(f) == [(62.5, 64.0, "oi")]


# ---------------------------------------------------------------- fetch_subs

def fake_ytdlp(tmp_path, produce_on_flag):
    calls = []

    def run(cmd, check=False):
        calls.append(cmd)
        if produce_on_flag in cmd:
            (tmp_path / "subs.pt.vtt").write_text(MANUAL_VTT, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    return run, calls


def test_fetch_subs_prefers_manual(tmp_path, monkeypatch):
    run, calls = fake_ytdlp(tmp_path, "--write-subs")
    monkeypatch.setattr(yt.subprocess, "run", run)
    segs = yt.fetch_subs("URL", "pt", tmp_path)
    assert segs[0][2] == "Olá, mundo."
    assert len(calls) == 1
    assert "pt-orig,pt,pt-BR" in calls[0]


def test_fetch_subs_falls_back_to_auto(tmp_path, monkeypatch):
    run, calls = fake_ytdlp(tmp_path, "--write-auto-subs")
    monkeypatch.setattr(yt.subprocess, "run", run)
    assert yt.fetch_subs("URL", None, tmp_path)
    assert [c[-2] for c in calls] == ["--write-subs", "--write-auto-subs"]


def test_fetch_subs_none_available(tmp_path, monkeypatch):
    run, _ = fake_ytdlp(tmp_path, "--nunca")
    monkeypatch.setattr(yt.subprocess, "run", run)
    assert yt.fetch_subs("URL", None, tmp_path) is None


# ---------------------------------------------------------------- main

def run_main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["yt-transcript", *argv])
    yt.main()


def test_main_local_file_uses_whisper(tmp_path, monkeypatch, capsys):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"")
    seen = {}

    def fake_transcribe(audio, model, lang, device):
        seen.update(audio=audio, model=model, lang=lang, device=device)
        return SEGMENTS

    monkeypatch.setattr(yt, "transcribe", fake_transcribe)
    monkeypatch.setattr(yt, "download_audio", lambda *a: pytest.fail("não deveria baixar"))
    run_main(monkeypatch, str(media), "--lang", "pt", "-m", "small")
    assert capsys.readouterr().out == "Primeira frase.\nSegunda frase.\n"
    assert seen == {"audio": media, "model": "small", "lang": "pt", "device": "auto"}


def test_main_subs_writes_output_file(tmp_path, monkeypatch):
    out = tmp_path / "out.srt"
    monkeypatch.setattr(yt, "fetch_subs", lambda url, lang, wd: SEGMENTS)
    monkeypatch.setattr(yt, "transcribe", lambda *a: pytest.fail("não deveria transcrever"))
    run_main(monkeypatch, "https://youtu.be/x", "--subs", "-f", "srt", "-o", str(out))
    assert out.read_text(encoding="utf-8").startswith("1\n00:00:00,000 --> 00:00:02,500\n")


def test_main_subs_missing_falls_back_to_whisper(tmp_path, monkeypatch, capsys):
    audio = tmp_path / "audio.m4a"
    monkeypatch.setattr(yt, "fetch_subs", lambda *a: None)
    monkeypatch.setattr(yt, "download_audio", lambda url, wd: audio)
    monkeypatch.setattr(yt, "transcribe", lambda a, *rest: SEGMENTS if a == audio else None)
    run_main(monkeypatch, "https://youtu.be/x", "--subs", "-f", "ts")
    assert capsys.readouterr().out.startswith("[00:00:00] Primeira frase.")


def test_help_runs_as_script():
    # executa o arquivo direto com python (sem uv) para garantir que --help funciona
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--subs" in r.stdout
