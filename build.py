#!/usr/bin/env python3
"""Sestaví časovou osu z tabulky v Markdownu do jednoho statického HTML souboru.

Použití:
    python3 build.py                                  # data/casova-osa.md -> dist/index.html (+ robots.txt)
    python3 build.py --data "Časová osa – události.md" --out "Časová osa.html" --no-robots

Staging je výchozí (noindex + robots.txt Disallow). Produkční build: PRODUCTION=1.
Všechny události jsou ve statickém HTML; JavaScript jen filtruje.
"""
import argparse
import datetime
import html
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LINES = {
    "cz-svaz": "Svaz junáků-skautů",
    "cz-soc": "Skauti-socialisté a Junáci volnosti",
    "de": "Pfadfinder (němečtí skauti)",
    "zid": "Židovští skauti",
    "kontext": "Kontext",
}
# značky z trezoru -> (klíč, text štítku)
VERIFY = {
    "✅": ("overeno", "Ověřeno v prameni"),
    "📘": ("dp", "Převzato z DP 2021"),
    "🤖": ("neovereno", "Neověřeno"),
    "❓": ("otevrene", "Otevřená otázka"),
    "🗣️": ("pametnik", "Ústní zdroj"),
    "🗣": ("pametnik", "Ústní zdroj"),
}
DP = {"ne": "Nové proti DP", "rozpor": "Rozpor s DP"}
MONTHS_GEN = ["", "ledna", "února", "března", "dubna", "května", "června", "července",
              "srpna", "září", "října", "listopadu", "prosince"]
MONTHS_NOM = ["", "leden", "únor", "březen", "duben", "květen", "červen", "červenec",
              "srpen", "září", "říjen", "listopad", "prosinec"]
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]️?")


def parse(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*\d{4}", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            raise SystemExit(f"Řádek má málo sloupců: {line[:80]}")
        date, precision, line_key, text, source, verify, dp = cells[:7]
        if line_key not in LINES:
            raise SystemExit(f"Neznámá linka „{line_key}“: {line[:80]}")
        rows.append(dict(date=date, precision=precision, line=line_key, text=text,
                         source=source, verify=verify, dp=dp))
    rows.sort(key=lambda r: (r["date"] + "-00-00")[:10])
    return rows


def inline_md(s):
    """Escapuje text, převede [text](url) na odkaz a ❓ na štítek otevřené otázky."""
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               r'<a href="\2" rel="noopener" target="_blank">\1</a>', s)
    s = s.replace("❓", '<strong class="q">Otevřené:</strong>')
    return EMOJI.sub("", s).strip()


def human_date(r):
    p = r["date"].split("-")
    if len(p) == 3:
        out = f"{int(p[2])}. {MONTHS_GEN[int(p[1])]} {p[0]}"
    elif len(p) == 2:
        out = f"{MONTHS_NOM[int(p[1])]} {p[0]}"
    else:
        out = p[0]
    return out


def iso(r):
    return r["date"]


def render_event(r):
    vkey, vlabel = VERIFY.get(r["verify"], ("neovereno", "Neověřeno"))
    tags = [f'<span class="tag tag--line" data-l="{r["line"]}">{LINES[r["line"]]}</span>',
            f'<span class="tag tag--{vkey}"><svg aria-hidden="true"><use href="#i-{vkey}"/></svg>{vlabel}</span>']
    if r["dp"] in DP:
        tags.append(f'<span class="tag tag--dp-{r["dp"]}">{DP[r["dp"]]}</span>')
    when = human_date(r)
    if r["precision"] == "tisk":
        when_note = '<span class="when-note">datum zprávy v tisku</span>'
    elif r["precision"] == "rok":
        when_note = '<span class="when-note">přesné datum neznámé</span>'
    else:
        when_note = ""
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", f'{when} {r["text"]} {r["source"]}')
    search = html.escape(EMOJI.sub("", plain).lower(), quote=True)
    return (
        f'<li class="ev ev--{r["precision"]}" data-l="{r["line"]}" data-v="{vkey}" '
        f'data-dp="{html.escape(r["dp"])}" data-s="{search}">'
        f'<p class="ev__meta"><time datetime="{iso(r)}">{when}</time>{when_note}</p>'
        f'<p class="ev__text">{inline_md(r["text"])}</p>'
        f'<p class="ev__tags">{"".join(tags)}</p>'
        f'<p class="ev__src"><span>Zdroj:</span> {inline_md(r["source"])}</p>'
        f'</li>'
    )


def build(data, out, robots, production):
    rows = parse(data)
    years = {}
    for r in rows:
        years.setdefault(r["date"][:4], []).append(r)

    year_nav = "".join(f'<li><a href="#r{y}">{y}</a></li>' for y in years)
    sections = "".join(
        f'<section class="year" id="r{y}" aria-labelledby="h{y}">'
        f'<h2 id="h{y}">{y}</h2><ol class="events">{"".join(render_event(r) for r in evs)}</ol></section>'
        for y, evs in years.items()
    )

    counts = {k: 0 for k in ("overeno", "dp", "neovereno")}
    for r in rows:
        k = VERIFY.get(r["verify"], ("neovereno",))[0]
        counts[k] = counts.get(k, 0) + 1
    new = sum(r["dp"] == "ne" for r in rows)
    conflict = sum(r["dp"] == "rozpor" for r in rows)
    first, last = rows[0]["date"][:4], rows[-1]["date"][:4]

    line_buttons = "".join(
        f'<button type="button" class="fbtn" data-group="l" data-key="{k}" aria-pressed="true">'
        f'<span class="dot" data-l="{k}" aria-hidden="true"></span>{v}</button>'
        for k, v in LINES.items())
    verify_buttons = "".join(
        f'<button type="button" class="fbtn" data-group="v" data-key="{k}" aria-pressed="true">{v}</button>'
        for k, v in (("overeno", "Ověřeno"), ("dp", "Z DP 2021"), ("neovereno", "Neověřeno")))

    tpl = (ROOT / "src" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "src" / "app.js").read_text(encoding="utf-8")
    robots_meta = "" if production else '<meta name="robots" content="noindex, nofollow">\n'

    page = (tpl
            .replace("{{ROBOTS}}", robots_meta)
            .replace("{{CSS}}", css)
            .replace("{{JS}}", js)
            .replace("{{RANGE}}", f"{first}–{last}")
            .replace("{{COUNT}}", str(len(rows)))
            .replace("{{OK}}", str(counts["overeno"]))
            .replace("{{DP}}", str(counts["dp"]))
            .replace("{{UNVERIFIED}}", str(counts["neovereno"]))
            .replace("{{NEW}}", str(new))
            .replace("{{CONFLICT}}", str(conflict))
            .replace("{{YEAR_NAV}}", year_nav)
            .replace("{{LINE_BUTTONS}}", line_buttons)
            .replace("{{VERIFY_BUTTONS}}", verify_buttons)
            .replace("{{SECTIONS}}", sections)
            .replace("{{DATE}}", datetime.date.today().strftime("%-d. %-m. %Y")))
    if "{{" in page:
        raise SystemExit("V šabloně zůstal nenahrazený zástupný text.")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    if robots:
        (out.parent / "robots.txt").write_text(
            "User-agent: *\nAllow: /\n" if production else "User-agent: *\nDisallow: /\n",
            encoding="utf-8")
    mode = "produkce" if production else "staging (noindex)"
    print(f"OK – {len(rows)} událostí, {len(years)} let, {mode} -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "casova-osa.md"))
    ap.add_argument("--out", default=str(ROOT / "dist" / "index.html"))
    ap.add_argument("--no-robots", action="store_true", help="nezapisovat robots.txt (lokální náhled)")
    a = ap.parse_args()
    build(a.data, a.out, not a.no_robots, os.environ.get("PRODUCTION") == "1")
