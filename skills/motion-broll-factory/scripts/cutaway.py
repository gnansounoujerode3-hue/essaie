#!/usr/bin/env python3
"""Cutaway réel depuis SON propre rush : crop serré + lente poussée sur une fenêtre.

Extrait un passage (souvent non gardé par le montage) recadré fort autour d'un
point → « B-roll vidéo » 100 % licence-clean (aucun réseau requis).
"""
import argparse
import shutil
import subprocess
import sys


def ffmpeg_exe():
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("--t0", type=float, required=True, help="début (s)")
    ap.add_argument("--t1", type=float, required=True, help="fin (s)")
    ap.add_argument("--zoom", type=float, default=1.7, help="recadrage de base")
    ap.add_argument("--push", type=float, default=0.10, help="poussée ajoutée sur la durée")
    ap.add_argument("--focus", default="0.5,0.5", help="point focal x,y en ratios")
    ap.add_argument("-o", default="cutaway.mp4")
    a = ap.parse_args()
    if a.t1 <= a.t0:
        sys.exit("--t1 doit suivre --t0")
    fx, fy = (float(v) for v in a.focus.split(","))
    dur = a.t1 - a.t0
    # Taille source (garantit un facteur ≥ 1080x1920 AVANT le crop final)
    import re as _re
    import subprocess as _sp
    probe = _sp.run([ffmpeg_exe(), "-hide_banner", "-i", a.input],
                    capture_output=True, text=True).stderr
    m = _re.search(r"(\d{2,5})x(\d{2,5})", probe)
    sw, sh = (int(m.group(1)), int(m.group(2))) if m else (1280, 720)
    z0 = max(a.zoom, 1.06 * 1080 / sw, 1.06 * 1920 / sh)
    # trim local → zoom animé (eval=frame) → crop 9:16 absolu (expr iw/iw-1080
    # uniquement : le var 'w' n'est pas résoluble dans ce build ffmpeg)
    vf = (
        f"trim=start={a.t0}:end={a.t1},setpts=PTS-STARTPTS,"
        f"scale=w='iw*{z0:.4f}*(1+{a.push}*t/{dur:.3f})':"
        f"h='ih*{z0:.4f}*(1+{a.push}*t/{dur:.3f})':eval=frame,"
        f"crop=w=1080:h=1920:x='(iw-1080)*{fx:.3f}':y='(ih-1920)*{fy:.3f}',"
        f"setsar=1,fps=30"
    )
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
           "-i", a.input,
           "-vf", vf, "-an", "-c:v", "libx264", "-crf", "18",
           "-preset", "veryfast", "-pix_fmt", "yuv420p", a.o]
    subprocess.run(cmd, check=True)
    print(f"écrit : {a.o} ({dur:.2f}s, zoom {a.zoom}→{a.zoom + a.push:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
