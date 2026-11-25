#!/usr/bin/env python3
"""Sestaví časovou osu z tabulky v Markdownu do jednoho statického HTML souboru.

Použití:
    python3 build.py                                  # data/casova-osa.md -> dist/index.html (+ robots.txt)
    python3 build.py --data "Časová osa – události.md" --out "Časová osa.html" --no-robots

Staging je výchozí (noindex + robots.txt Disallow). Produkční build: PRODUCTION=1.
Všechny události jsou ve statickém HTML; JavaScript jen filtruje.
"""
import argparse
import json
import shutil
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


def picture(fe, name, sizes, cls="", lazy=True, base=""):
    im = fe["images"][name]
    load = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return (f'<img class="{cls}" src="{base}img/{name}-1400.webp" '
            f'srcset="{base}img/{name}-700.webp 700w, {base}img/{name}-1400.webp 1400w" sizes="{sizes}" '
            f'width="{im["w"]}" height="{im["h"]}" alt="{html.escape(im["alt"])}"{load}>')


def feature_for(r, fe):
    f = fe["features"].get(r["date"])
    if f and (not f.get("match") or f["match"] in r["text"]):
        return f
    return None


def render_event(r, fe, side, base):
    vkey, vlabel = VERIFY.get(r["verify"], ("neovereno", "Neověřeno"))
    tags = [f'<span class="tag tag--line" data-l="{r["line"]}"><span class="dot" data-l="{r["line"]}" aria-hidden="true"></span>{LINES[r["line"]]}</span>',
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
    attrs = (f'data-l="{r["line"]}" data-v="{vkey}" data-dp="{html.escape(r["dp"])}" data-s="{search}"')
    body = (f'<p class="ev__text">{inline_md(r["text"])}</p>'
            f'<p class="ev__tags">{"".join(tags)}</p>'
            f'<p class="ev__src"><span>Zdroj:</span> {inline_md(r["source"])}</p>')
    f = feature_for(r, fe)
    if f:
        fig = ""
        if f.get("img"):
            fig = (f'<figure class="feat__fig">{picture(fe, f["img"], "(min-width: 900px) 540px, 100vw", base=base)}'
                   f'<figcaption>{html.escape(fe["credit"])}</figcaption></figure>')
        cls = "feat" + (" feat--img" if fig else " feat--text") + (" feat--rev" if side else "")
        return (f'<li class="ev ev--{r["precision"]} {cls}" {attrs}>{fig}<div class="feat__body">'
                f'<p class="ev__meta"><time datetime="{iso(r)}">{when}</time>{when_note}</p>'
                f'<h3 class="feat__title">{html.escape(f["title"])}</h3>{body}</div></li>')
    return (f'<li class="ev ev--{r["precision"]}" {attrs}>'
            f'<p class="ev__meta"><time datetime="{iso(r)}">{when}</time>{when_note}</p>'
            f'<div class="ev__main">{body}</div></li>')


def build(data, out, robots, production, base=""):
    rows = parse(data)
    fe = json.loads((ROOT / "src" / "featured.json").read_text(encoding="utf-8"))
    chapters = fe["chapters"]
    years = {}
    for r in rows:
        years.setdefault(r["date"][:4], []).append(r)

    year_nav = "".join(f'<li data-y="{y}"><a href="#r{y}">{y}</a></li>' for y in years)
    chapter_nav = "".join(
        f'<li data-y="{y}"><a class="bubble{" bubble--dark" if c.get("dark") else ""}" href="#r{y}">'
        f'<span class="bubble__y">{y}</span><span class="bubble__l">{html.escape(c["label"])}</span></a></li>'
        for y, c in chapters.items() if y in years)
    side = [0]

    def ev(r):
        if feature_for(r, fe):
            side[0] ^= 1
        return render_event(r, fe, side[0], base)

    def head(y):
        c = chapters.get(y)
        if not c:
            return f'<header class="year__head"><h2 id="h{y}" class="year__num">{y}</h2></header>'
        dark = " year__head--dark" if c.get("dark") else ""
        return (f'<header class="year__head year__head--chapter{dark}"><h2 id="h{y}" class="year__num">{y}</h2>'
                f'<p class="year__title">{html.escape(c["title"])}</p></header>')

    sections = "".join(
        f'<section class="year" id="r{y}" aria-labelledby="h{y}">{head(y)}'
        f'<ol class="events">{"".join(ev(r) for r in evs)}</ol></section>'
        for y, evs in years.items()
    )
    hero = fe["hero"]
    hero_html = (picture(fe, hero["main"], "(min-width: 900px) 560px, 100vw", "hero__main", lazy=False, base=base)
                 + "".join(picture(fe, n, "200px", f"hero__small hero__small--{i}", base=base) for i, n in enumerate(hero["small"])))

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
            .replace("{{CHAPTER_NAV}}", chapter_nav)
            .replace("{{HERO_IMG}}", hero_html)
            .replace("{{CREDIT}}", html.escape(fe["credit"]))
            .replace("{{BASE}}", base)
            .replace("{{YEARS}}", str(int(last) - int(first) + 1))
            .replace("{{LINE_BUTTONS}}", line_buttons)
            .replace("{{VERIFY_BUTTONS}}", verify_buttons)
            .replace("{{SECTIONS}}", sections)
            .replace("{{DATE}}", datetime.date.today().strftime("%-d. %-m. %Y")))
    if "{{" in page:
        raise SystemExit("V šabloně zůstal nenahrazený zástupný text.")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    if not base:
        for d in ("img", "fonts"):
            shutil.copytree(ROOT / "src" / d, out.parent / d, dirs_exist_ok=True)
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
    ap.add_argument("--asset-base", default="", help="URL webu, odkud brát obrázky a písma (náhled v trezoru)")
    a = ap.parse_args()
    build(a.data, a.out, not a.no_robots, os.environ.get("PRODUCTION") == "1", a.asset_base)
