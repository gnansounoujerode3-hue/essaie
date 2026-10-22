#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
montage_marketing.py - RAW VIDEO IN, ONE FINISHED MARKETING VIDEO OUT.
Usage:
    python3 montage_marketing.py "raw_video.mp4" --out-dir ./output
LAST line printed on success:  FINAL_VIDEO=/full/path/to/result.mp4
LAST line printed on failure:  MONTAGE_ECHEC: <reason>
Needs: python3 + ffmpeg.
Optional: faster-whisper (subtitles + smart cuts), opencv-python-headless (face framing).
"""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
FFMPEG = None
WORK = None
LOGFILE = os.path.join(tempfile.gettempdir(), "montage_last_log.txt")
PIPE = subprocess.PIPE
FPS = 30
HALF = 0.5 / FPS
def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
def die(msg):
    log("FATAL: " + msg)
    print("MONTAGE_ECHEC: " + msg, flush=True)
    sys.exit(1)

def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
def ffmpeg_filters():
    p = subprocess.run([FFMPEG, "-hide_banner", "-filters"], stdout=PIPE, stderr=PIPE)
    txt = p.stdout.decode("utf-8", "replace")
    return set(re.findall(r"^\s*[A-Za-z.|]{3}\s+(\S+)\s", txt, re.M))
def probe(path):
    """Read basic info with 'ffmpeg -i' (no ffprobe needed)."""
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", path], stdout=PIPE, stderr=PIPE)
    txt = p.stderr.decode("utf-8", "replace")
    info = {"dur": 0.0, "video": False, "audio": False, "w": 0, "h": 0, "hdr": False}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", txt)
    if m:
        info["dur"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    for line in txt.splitlines():
        if "Stream #" not in line:
            continue
        if " Video:" in line and "attached pic" not in line and not info["video"]:
            info["video"] = True
            m = re.search(r",\s*(\d{2,5})x(\d{2,5})", line)
            if m:
                info["w"], info["h"] = int(m.group(1)), int(m.group(2))
            if "arib-std-b67" in line or "smpte2084" in line:
                info["hdr"] = True
        elif " Audio:" in line:
            info["audio"] = True
    return info
def run_ffmpeg(args, total_sec, label):
    """Run ffmpeg, print progress every 10 s. Returns (ok, stderr_text)."""
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-progress", "pipe:1"] + args
    log(label + " ...")
    errpath = os.path.join(WORK, "ffmpeg_stderr.txt")
    t0 = time.time()
    last = 0.0
    with open(errpath, "w") as ef:
        p = subprocess.Popen(cmd, cwd=WORK, stdout=PIPE, stderr=ef,
                             universal_newlines=True)
        for line in p.stdout:
            if line.startswith("out_time="):
                m = re.match(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
                if m and total_sec > 0 and time.time() - last > 10:
                    cur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                    log("%s: %d%%" % (label, min(99, int(100 * cur / total_sec))))
                    last = time.time()
        p.wait()
    with open(errpath, "r", errors="replace") as ef:
        err = ef.read()
    if p.returncode != 0:
        log("ffmpeg error: " + err.strip()[-700:])
        return False, err
    log("%s: done in %d s" % (label, time.time() - t0))
    return True, err
# ---------------------------------------------------------------- STEP 1
def normalize(src, dst, info, filters):
    vf = ["fps=30",
          "scale='min(2560,iw)':'min(2560,ih)':force_original_aspect_ratio=decrease"
          ":force_divisible_by=2"]
    if info["hdr"]:
        if "zscale" in filters and "tonemap" in filters:
            vf.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                      "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv")
            log("HDR detected: tone-mapping to SDR")
        else:

            log("HDR detected but zscale/tonemap missing: colors may look flat")
    vf.append("format=yuv420p")
    vf.append("setsar=1")
    args = ["-i", src, "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn",
            "-vf", ",".join(vf),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p"]
    if info["audio"]:
        args += ["-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2"]
    args.append(dst)
    ok, _ = run_ffmpeg(args, info["dur"], "Step 1/6 normalize")
    return ok
# ---------------------------------------------------------------- STEP 2-3
def extract_wav(src, dst, dur):
    ok, _ = run_ffmpeg(["-i", src, "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "pcm_s16le", dst], dur, "Step 2/6 audio")
    return ok
BAD_PHRASES = re.compile(r"amara\.org|sous-?titr|subtitles? by|subtitled by|transcribed by",
                         re.I)
def transcribe(wav, lang, model_size, dur):
    """Return (segments, language). Each segment: text, s, e, words[{w,s,e,p}]."""
    from faster_whisper import WhisperModel
    sizes = [model_size]
    if model_size != "base":
        sizes.append("base")
    model = None
    for size in sizes:
        try:
            log("Loading Whisper model '%s' (first time = download)" % size)
            model = WhisperModel(size, device="cpu", compute_type="int8",
                                 cpu_threads=min(os.cpu_count() or 2, 8))
            break
        except Exception as ex:
            log("Model '%s' failed: %s" % (size, str(ex)[:200]))
    if model is None:
        raise RuntimeError("no whisper model could be loaded")
    segs, info = model.transcribe(
        wav, language=None if lang == "auto" else lang, word_timestamps=True,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 350},
        beam_size=3, condition_on_previous_text=False)
    out = []
    for s in segs:
        words = []
        for w in (s.words or []):
            txt = w.word.strip()
            if txt:
                words.append({"w": txt, "s": float(w.start), "e": float(w.end),
                              "p": float(w.probability)})
        if not words:
            continue
        text = s.text.strip()
        if BAD_PHRASES.search(text) and (s.end >= dur - 8.0 or s.start <= 1.0):
            log("Dropped hallucinated segment: " + text[:60])
            continue
        out.append({"text": text, "s": float(s.start), "e": float(s.end), "words": words})
    return out, info.language
def norm_text(t):
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()
def is_retake(a, b):
    """a, b = lists of words. True if 'a' is an earlier take of what 'b' says."""
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    matched = sum(x.size for x in m.get_matching_blocks())
    contain = matched / float(len(a))
    ratio = 2.0 * matched / float(len(a) + len(b))
    return (contain >= 0.95 and len(b) >= 0.7 * len(a)) or ratio >= 0.90
def drop_retakes(segs):
    """If a sentence is said again right after, keep only the LAST take."""
    keep = [True] * len(segs)
    for i in range(len(segs)):

        a = norm_text(segs[i]["text"]).split()
        if len(a) < 4:
            continue
        for j in range(i + 1, min(i + 4, len(segs))):
            if segs[j]["s"] - segs[i]["e"] > 25.0:
                break
            b = norm_text(segs[j]["text"]).split()
            if len(b) < 3:
                continue
            if is_retake(a, b):
                keep[i] = False
                log("Retake removed: '%s'" % " ".join(a)[:60])
                break
    return [s for s, k in zip(segs, keep) if k]
# ---------------------------------------------------------------- STEP 4
def build_segments(words, dur, gap, pb, pa):
    """Speech islands from word times. Pauses longer than 'gap' are cut."""
    isl = []
    cs = ce = None
    for w in words:
        if cs is None:
            cs, ce = w["s"], w["e"]
        elif w["s"] - ce > gap:
            isl.append([cs, ce])
            cs, ce = w["s"], w["e"]
        else:
            ce = max(ce, w["e"])
    if cs is not None:
        isl.append([cs, ce])
    return pad_and_merge(isl, dur, pb, pa)
def pad_and_merge(isl, dur, pb, pa):
    out = []
    for s, e in isl:
        s = max(0.0, s - pb)
        e = min(dur, e + pa)
        if e - s < 0.25:
            continue
        if out and s <= out[-1][1] + 0.02:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]
def detect_speech_islands(src, dur, gap, pb, pa):
    """Fallback without Whisper: use ffmpeg silencedetect."""
    base = [FFMPEG, "-hide_banner", "-nostats", "-i", src, "-vn", "-af"]
    p = subprocess.run(base + ["volumedetect", "-f", "null", "-"], stdout=PIPE, stderr=PIPE)
    txt = p.stderr.decode("utf-8", "replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", txt)
    mean = float(m.group(1)) if m else -30.0
    thr = max(-50.0, min(-30.0, mean - 12.0))
    log("Silence threshold: %.0f dB" % thr)
    sd = "silencedetect=noise=%ddB:d=%.2f" % (thr, gap)
    p = subprocess.run(base + [sd, "-f", "null", "-"], stdout=PIPE, stderr=PIPE)
    txt = p.stderr.decode("utf-8", "replace")
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", txt)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", txt)]
    sil = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else dur
        sil.append((max(0.0, s), min(dur, e)))
    isl = []
    pos = 0.0
    for s, e in sil:
        if s - pos > 0.05:
            isl.append([pos, s])
        pos = max(pos, e)
    if dur - pos > 0.05:
        isl.append([pos, dur])
    return pad_and_merge(isl, dur, pb, pa)
# ---------------------------------------------------------------- FRAMING
def face_center(work, dur):
    """Return (median_x_fraction, spread, found_ratio) or None if OpenCV is missing."""
    try:

        import cv2
    except Exception:
        return None
    xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    casc = cv2.CascadeClassifier(xml)
    xs = []
    n = 10
    for i in range(n):
        t = dur * (i + 0.5) / n
        img = os.path.join(WORK, "face%02d.jpg" % i)
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", "%.2f" % t, "-i", work, "-frames:v", "1",
                        "-vf", "scale=640:-2", img], stdout=PIPE, stderr=PIPE)
        im = cv2.imread(img)
        if im is None:
            continue
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        faces = casc.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + w / 2.0) / float(im.shape[1]))
    ratio = len(xs) / float(n)
    if not xs:
        return (0.5, 1.0, 0.0)
    xs.sort()
    return (xs[len(xs) // 2], xs[-1] - xs[0], ratio)
def plan_reframe(fmt, sw, sh, work, dur, force_fit=False):
    """Return dict: W, H, mode ('crop' or 'fit'), rect (x, y, w, h) in source pixels."""
    sw -= sw % 2
    sh -= sh % 2
    if fmt == "keep":
        return {"W": sw, "H": sh, "mode": "crop", "rect": (0, 0, sw, sh)}
    W, H = {"vertical": (1080, 1920), "square": (1080, 1080),
            "horizontal": (1920, 1080)}[fmt]
    ta = W / float(H)
    sa = sw / float(sh)
    full = (0, 0, sw, sh)
    if abs(sa - ta) < 0.02:
        return {"W": W, "H": H, "mode": "crop", "rect": full}
    if sa < ta or force_fit:
        log("Blurred-background fit (nothing is cropped)")
        return {"W": W, "H": H, "mode": "fit", "rect": full}
    cw = int(round(sh * ta / 2.0)) * 2
    frac = cw / float(sw)
    fc = face_center(work, dur)
    if fc is None:
        log("OpenCV missing: centered crop")
        fx = 0.5
    else:
        fx, spread, ratio = fc
        log("Face check: found in %d%% of frames, x=%.2f, spread=%.2f" %
            (int(ratio * 100), fx, spread))
        if ratio < 0.3 or spread > 0.7 * frac:
            log("No stable face: blurred-background fit (nothing is cropped)")
            return {"W": W, "H": H, "mode": "fit", "rect": full}
    cx = int(round(fx * sw - cw / 2.0))
    cx = max(0, min(sw - cw, cx))
    cx -= cx % 2
    return {"W": W, "H": H, "mode": "crop", "rect": (cx, 0, cw, sh)}
def snap_segments(segs, dur):
    """Align cuts on the frame grid: every segment = a whole number of frames."""
    maxk = int(dur * FPS)
    out = []
    for s, e in segs:
        ks = max(0, int(round(s * FPS)))
        ke = min(maxk, int(round(e * FPS)))
        if ke - ks < 3:
            continue
        if out and ks <= out[-1][1]:
            out[-1][1] = max(out[-1][1], ke)
        else:
            out.append([ks, ke])
    res = [(ks / float(FPS), ke / float(FPS)) for ks, ke in out]
    return res or [(0.0, maxk / float(FPS))]
def zoom_rect(rect, z):

    x, y, w, h = rect
    zw = int(w / z / 2.0) * 2
    zh = int(h / z / 2.0) * 2
    zx = x + (w - zw) // 2
    zy = y + (h - zh) // 2
    return (zx - zx % 2, zy - zy % 2, zw, zh)
def zoom_flags(segs):
    flags = []
    on = False
    for i in range(len(segs)):
        if i > 0 and (segs[i - 1][1] - segs[i - 1][0]) >= 1.2:
            on = not on
        flags.append(on)
    return flags
# ---------------------------------------------------------------- SUBTITLES
def pick_font():
    fam = "Arial"
    fontsdir = None
    n = 0
    if shutil.which("fc-list"):
        try:
            n = len(subprocess.run(["fc-list"], stdout=PIPE, stderr=PIPE,
                                   timeout=60).stdout.splitlines())
        except Exception:
            n = 0
    if n > 0 and shutil.which("fc-match"):
        try:
            out = subprocess.run(["fc-match", "-f", "%{family}", "sans-serif:bold"],
                                 stdout=PIPE, stderr=PIPE, timeout=30)
            name = out.stdout.decode("utf-8", "replace").strip()
            if name:
                fam = name.split(",")[0].strip()
        except Exception:
            pass
    if n == 0:
        try:
            import matplotlib
            d = os.path.join(os.path.dirname(matplotlib.__file__),
                             "mpl-data", "fonts", "ttf")
            if os.path.isdir(d):
                return "DejaVu Sans", d
        except Exception:
            pass
        return None, None
    return fam, fontsdir
def clean_word(t):
    t = t.replace("\\", "").replace("{", "").replace("}", "").replace("\n", " ").strip()
    t = re.sub(r"[.,;:]+$", "", t)
    return t.upper()
def ass_time(t):
    cs = int(round(max(0.0, t) * 100))
    h = cs // 360000
    cs -= h * 360000
    m = cs // 6000
    cs -= m * 6000
    s = cs // 100
    cs -= s * 100
    return "%d:%02d:%02d.%02d" % (h, m, s, cs)
def words_on_timeline(words, segs):
    offs = []
    acc = 0.0
    for s, e in segs:
        offs.append(acc)
        acc += e - s
    out = []
    for w in words:
        for i, (s, e) in enumerate(segs):
            if s - 0.05 <= w["s"] <= e:
                ts = offs[i] + max(0.0, w["s"] - s)
                te = offs[i] + min(w["e"], e) - s
                if te <= ts:

                    te = ts + 0.15
                txt = clean_word(w["w"])
                if txt:
                    brk = bool(re.search(r"[.?!]$", w["w"].strip()))
                    out.append({"t": txt, "s": ts, "e": te, "brk": brk})
                break
    return out, acc
def chunk_words(ws, max_words, max_chars):
    chunks = []
    cur = []
    for w in ws:
        if cur:
            txt = " ".join([x["t"] for x in cur] + [w["t"]])
            if (len(cur) >= max_words or len(txt) > max_chars or cur[-1]["brk"]
                    or w["s"] - cur[-1]["e"] > 0.5):
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks
def write_ass(path, W, H, ws, total, font, hook, cta):
    portrait = H > W
    fs = int(round(min(W, H) * (0.072 if portrait else 0.058)))
    mv = int(H * (0.21 if portrait else 0.08))
    outline = max(3, int(fs * 0.08))
    hfs = int(fs * 0.85)
    hmv = int(H * (0.09 if portrait else 0.06))
    if portrait:
        max_words, max_chars = 3, 18
    elif W == H:
        max_words, max_chars = 4, 24
    else:
        max_words, max_chars = 5, 32
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: %d" % W, "PlayResY: %d" % H,
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Cap,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,"
        "1,%d,2,2,60,60,%d,1" % (font, fs, outline, mv),
        "Style: Hook,%s,%d,&H00000000,&H00000000,&H0000D7FF,&H00000000,-1,0,0,0,100,100,0,0,"
        "3,%d,0,8,60,60,%d,1" % (font, hfs, int(hfs * 0.25), hmv),
        "Style: Cta,%s,%d,&H00FFFFFF,&H00FFFFFF,&H001D6BF2,&H00000000,-1,0,0,0,100,100,0,0,"
        "3,%d,0,8,60,60,%d,1" % (font, hfs, int(hfs * 0.25), hmv),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    chunks = chunk_words(ws, max_words, max_chars)
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else total
        for i, w in enumerate(ch):
            st = w["s"]
            if i + 1 < len(ch):
                en = ch[i + 1]["s"]
            else:
                en = min(w["e"] + 0.15, max(nxt, st + 0.05))
            if en - st < 0.05:
                en = st + 0.05
            parts = []
            for j, x in enumerate(ch):
                if j == i:
                    parts.append("{\\c&H00D7FF&}" + x["t"] + "{\\c&HFFFFFF&}")
                else:
                    parts.append(x["t"])
            lines.append("Dialogue: 0,%s,%s,Cap,,0,0,0,,%s" %
                         (ass_time(st), ass_time(en), " ".join(parts)))
    if hook:
        lines.append("Dialogue: 1,%s,%s,Hook,,0,0,0,,%s" %
                     (ass_time(0.0), ass_time(min(3.0, total)), clean_word(hook)))
    if cta and total > 6.0:
        lines.append("Dialogue: 1,%s,%s,Cta,,0,0,0,,%s" %
                     (ass_time(total - 3.0), ass_time(total), clean_word(cta)))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

# ---------------------------------------------------------------- RENDER
def build_graph(segs, plan, opt, has_audio, subs_filter, music):
    W, H, mode, rect = plan["W"], plan["H"], plan["mode"], plan["rect"]
    n = len(segs)
    flags = [False] * n
    if opt["zoom"] and mode == "crop":
        flags = zoom_flags(segs)
    parts = []
    for i, (s, e) in enumerate(segs):
        v = "[0:v]trim=start=%.5f:end=%.5f,setpts=PTS-STARTPTS" % (max(0.0, s - HALF),
                                                                     e - HALF)
        if mode == "crop":
            x, y, w, h = zoom_rect(rect, 1.10) if flags[i] else rect
            v += ",crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos" % (w, h, x, y, W, H)
        v += ",setsar=1[v%d]" % i
        parts.append(v)
        if has_audio:
            d = e - s
            f = min(0.02, d / 4.0)
            parts.append("[0:a]atrim=start=%.5f:end=%.5f,asetpts=PTS-STARTPTS,"
                         "afade=t=in:st=0:d=%.3f,afade=t=out:st=%.3f:d=%.3f[a%d]" %
                         (s, e, f, max(0.0, d - f), f, i))
    ins = "".join(("[v%d][a%d]" % (i, i)) if has_audio else ("[v%d]" % i) for i in range(n))
    if has_audio:
        parts.append("%sconcat=n=%d:v=1:a=1[vc][ac]" % (ins, n))
    else:
        parts.append("%sconcat=n=%d:v=1:a=0[vc]" % (ins, n))
    post = "null"
    if opt["look"]:
        post = "eq=contrast=1.04:saturation=1.10,unsharp=5:5:0.4:5:5:0.0"
    if mode == "fit":
        parts.append("[vc]split=2[b1][f1]")
        parts.append("[b1]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                     "scale=trunc(iw/16)*2:trunc(ih/16)*2,boxblur=3:2,scale=%d:%d,"
                     "eq=brightness=-0.08[bg]" % (W, H, W, H, W, H))
        parts.append("[f1]scale=%d:%d:force_original_aspect_ratio=decrease:"
                     "force_divisible_by=2[fg]" % (W, H))
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2,%s%s[vout]" % (post, subs_filter))
    else:
        parts.append("[vc]%s%s[vout]" % (post, subs_filter))
    if has_audio:
        chain = "highpass=f=80"
        if opt["denoise"]:
            chain += ",afftdn=nr=8:nf=-45:tn=1"
        chain += ",acompressor=threshold=0.125:ratio=3:attack=10:release=120:makeup=1.5"
        norm = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
        if music:
            parts.append("[ac]%s,asplit=2[vo1][vo2]" % chain)
            parts.append("[1:a]aresample=48000,aformat=channel_layouts=stereo,"
                         "volume=0.20[mus]")
            parts.append("[mus][vo2]sidechaincompress=threshold=0.02:ratio=10:"
                         "attack=15:release=400[duck]")
            parts.append("[vo1][duck]amix=inputs=2:duration=first:normalize=0,%s[aout]"
                         % norm)
        else:
            parts.append("[ac]%s,%s[aout]" % (chain, norm))
    return ";\n".join(parts) + "\n"
def render(segs, plan, opt, info, words, level_name, music, hook, cta, filters):
    """Build graph, run ffmpeg, validate. Returns path or None."""
    has_audio = info["audio"]
    segs = snap_segments(segs, info["dur"])
    ws, total = words_on_timeline(words, segs) if words else ([], 0.0)
    expected = sum(e - s for s, e in segs)
    subs_filter = ""
    if opt["subs"] and ws and "ass" in filters:
        font, fontsdir = pick_font()
        if font is None:
            log("No font found: subtitles skipped (install fonts-dejavu-core)")
        else:
            write_ass(os.path.join(WORK, "subs.ass"), plan["W"], plan["H"], ws, expected,
                      font, hook, cta)
            subs_filter = ",ass=filename='subs.ass'"
            if fontsdir:
                subs_filter += ":fontsdir='%s'" % fontsdir
            log("Subtitles: %d words, font '%s'" % (len(ws), font))
    elif (hook or cta) and opt["subs"] and "ass" in filters:
        font, fontsdir = pick_font()

        if font is not None:
            write_ass(os.path.join(WORK, "subs.ass"), plan["W"], plan["H"], [], expected,
                      font, hook, cta)
            subs_filter = ",ass=filename='subs.ass'"
            if fontsdir:
                subs_filter += ":fontsdir='%s'" % fontsdir
    use_music = bool(music) and has_audio
    graph = build_graph(segs, plan, opt, has_audio, subs_filter, use_music)
    with open(os.path.join(WORK, "graph.txt"), "w") as f:
        f.write(graph)
    out = os.path.join(WORK, "render_%s.mp4" % level_name)
    base = ["-i", os.path.join(WORK, "work.mp4")]
    if use_music:
        base += ["-stream_loop", "-1", "-i", music]
    tail = ["-map", "[vout]"]
    if has_audio:
        tail += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    tail += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
             "-r", "30", "-movflags", "+faststart", out]
    ok = False
    for flag in ("-filter_complex_script", "-/filter_complex"):
        ok, err = run_ffmpeg(base + [flag, "graph.txt"] + tail, expected,
                             "Step 5/6 render [%s]" % level_name)
        if ok or not re.search(r"nrecognized option|not found", err):
            break
    if not ok:
        return None
    res = probe(out)
    if not res["video"] or (has_audio and not res["audio"]):
        log("Check failed: missing stream")
        return None
    tol = max(2.0, expected * 0.1)
    if res["dur"] < min(1.0, expected * 0.5) or abs(res["dur"] - expected) > tol:
        log("Check failed: duration %.1f s, expected %.1f s" % (res["dur"], expected))
        return None
    if os.path.getsize(out) < 20000:
        log("Check failed: file too small")
        return None
    log("Checks OK: %.1f s, %dx%d" % (res["dur"], res["w"], res["h"]))
    return out
def render_basic(plan, info):
    """Last resort: one simple ffmpeg command, no cuts, no fancy filters."""
    W, H = plan["W"], plan["H"]
    if plan["mode"] == "crop":
        x, y, w, h = plan["rect"]
        vf = "crop=%d:%d:%d:%d,scale=%d:%d" % (w, h, x, y, W, H)
    else:
        vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
              "pad=%d:%d:(ow-iw)/2:(oh-ih)/2" % (W, H, W, H))
    out = os.path.join(WORK, "render_basic.mp4")
    args = ["-i", os.path.join(WORK, "work.mp4"), "-vf", vf + ",format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    if info["audio"]:
        args += ["-c:a", "aac", "-b:a", "192k"]
    args += ["-movflags", "+faststart", out]
    ok, _ = run_ffmpeg(args, info["dur"], "Step 5/6 render [basic]")
    return out if ok else None
# ---------------------------------------------------------------- MAIN
def main():
    global FFMPEG, WORK
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--format", default="vertical",
                    choices=["vertical", "square", "horizontal", "keep"])
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--model", default="small")
    ap.add_argument("--gap", type=float, default=0.45)
    ap.add_argument("--fit", action="store_true", help="never crop (blurred background)")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--no-zoom", action="store_true")
    ap.add_argument("--no-retakes", action="store_true")
    ap.add_argument("--no-denoise", action="store_true")
    ap.add_argument("--no-whisper", action="store_true")
    ap.add_argument("--music", default=None)
    ap.add_argument("--hook", default=None)
    ap.add_argument("--cta", default=None)

    ap.add_argument("--words-json", default=None, help="test only")
    ap.add_argument("--keep-temp", action="store_true")
    args = ap.parse_args()
    try:
        open(LOGFILE, "w").close()
    except Exception:
        pass
    FFMPEG = find_ffmpeg()
    if not FFMPEG:
        die("ffmpeg not found (install ffmpeg or: pip install imageio-ffmpeg)")
    src = os.path.abspath(args.input)
    if not os.path.isfile(src):
        die("input file not found: " + src)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    music = os.path.abspath(args.music) if args.music else None
    if music and not os.path.isfile(music):
        log("Music file not found, ignored: " + music)
        music = None
    try:
        WORK = tempfile.mkdtemp(prefix="montage_work_", dir=os.getcwd())
    except Exception:
        WORK = tempfile.mkdtemp(prefix="montage_work_")
    filters = ffmpeg_filters()
    info0 = probe(src)
    if not info0["video"]:
        die("no video stream in input file")
    log("Input: %s (%.1f s, %dx%d, audio=%s)" %
        (os.path.basename(src), info0["dur"], info0["w"], info0["h"], info0["audio"]))
    work = os.path.join(WORK, "work.mp4")
    if not normalize(src, work, info0, filters):
        die("could not read/convert the input video")
    info = probe(work)
    dur = info["dur"]
    if dur <= 0.5:
        die("video too short or unreadable")
    # ---- speech analysis (Whisper, else silencedetect)
    words = []
    wseg = []
    state = "off"
    if info["audio"] and not args.no_whisper:
        try:
            if args.words_json:
                with open(args.words_json, "r", encoding="utf-8") as f:
                    wseg = json.load(f)
            else:
                wav = os.path.join(WORK, "audio16k.wav")
                if not extract_wav(work, wav, dur):
                    raise RuntimeError("audio extraction failed")
                wseg, lang = transcribe(wav, args.lang, args.model, dur)
                log("Step 3/6 transcription: %d segments, language=%s" % (len(wseg), lang))
            state = "ok"
        except Exception as ex:
            log("Whisper unavailable (%s): continuing without subtitles" % str(ex)[:200])
            state = "failed"
    if state == "ok" and not args.no_retakes:
        wseg = drop_retakes(wseg)
    for s in wseg:
        words.extend(s["words"])
    words.sort(key=lambda w: w["s"])
    pb, pa = 0.15, 0.25
    if not info["audio"]:
        segs = [(0.0, dur)]
    elif state == "ok":
        segs = build_segments(words, dur, args.gap, pb, pa) if words else [(0.0, dur)]
    else:
        segs = detect_speech_islands(work, dur, args.gap, pb, pa) or [(0.0, dur)]
    kept = sum(e - s for s, e in segs)
    if kept < 0.15 * dur:
        log("Suspicious cut (only %.0f%% kept): keeping whole video" % (100 * kept / dur))
        segs = [(0.0, dur)]
        kept = dur
    log("Step 4/6 plan: %d segments, %.1f s kept of %.1f s" % (len(segs), kept, dur))
    plan = plan_reframe(args.format, info["w"], info["h"], work, dur, args.fit)
    log("Format: %dx%d (%s)" % (plan["W"], plan["H"], plan["mode"]))

    base_opt = {"subs": not args.no_subs, "zoom": not args.no_zoom,
                "denoise": not args.no_denoise, "look": True}
    levels = [("full", segs, base_opt, words, music, args.hook, args.cta),
              ("safe", segs, {"subs": False, "zoom": False, "denoise": False,
                              "look": False}, [], None, None, None),
              ("plain", [(0.0, dur)], {"subs": False, "zoom": False, "denoise": False,
                                       "look": False}, [], None, None, None)]
    result = None
    for name, sg, opt, wd, mus, hk, ct in levels:
        try:
            result = render(sg, plan, opt, info, wd, name, mus, hk, ct, filters)
        except Exception as ex:
            log("Level '%s' crashed: %s" % (name, str(ex)[:300]))
            result = None
        if result:
            break
        log("Level '%s' failed, trying a simpler level" % name)
    if not result:
        log("Trying the last-resort level 'basic'")
        result = render_basic(plan, info)
    if not result:
        log("Work folder kept for debugging: " + WORK)
        die("all render levels failed (see log: %s)" % LOGFILE)
    stem = os.path.splitext(os.path.basename(src))[0]
    final = os.path.join(out_dir, stem + "_marketing.mp4")
    shutil.copyfile(result, final)
    if not args.keep_temp:
        shutil.rmtree(WORK, ignore_errors=True)
    log("Step 6/6 done")
    print("FINAL_VIDEO=" + final, flush=True)
if __name__ == "__main__":
    main()
# END_OF_SCRIPT_OK
