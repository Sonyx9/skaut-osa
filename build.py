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
SHORT = {"cz-svaz": "Junáci (Svaz)", "cz-soc": "Dělničtí skauti", "de": "Pfadfinder",
         "zid": "Židovští skauti", "kontext": "Kontext"}
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
    s = re.sub(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\((https?://[^)\s]+)\)",
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


def parse_cards(path):
    """Karty osob/míst: sekce '## Název' s odrážkami '- klíč: hodnota'."""
    cards = []
    p = Path(path)
    if not p.exists():
        return cards
    cur = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = {"name": line[3:].strip()}
            cards.append(cur)
        elif cur is not None:
            m = re.match(r"^-\s*([^:]+):\s*(.*)$", line)
            if m:
                cur[m.group(1).strip()] = m.group(2).strip()
    for c in cards:
        if not c.get("id") or not c.get("hledat"):
            raise SystemExit(f"Karta „{c['name']}“ nemá id nebo hledat.")
        c["re"] = re.compile(c["hledat"])
        c["events"] = []
    return cards


def link_cards(rows, people, places):
    seen = {}
    for r in rows:
        k = seen[r["date"]] = seen.get(r["date"], 0) + 1
        r["id"] = f"e{r['date']}" + (f"-{k}" if k > 1 else "")
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", r["text"])
        r["people"] = [c for c in people if c["re"].search(plain)]
        r["places"] = [c for c in places if c["re"].search(plain)]
        for c in r["people"] + r["places"]:
            c["events"].append(r)


def chips(r):
    out = []
    if r.get("people"):
        out.append('<span class="ev__rel-k">Osoby:</span> ' + ", ".join(
            f'<a href="osobnosti.html#{c["id"]}">{html.escape(c["name"])}</a>' for c in r["people"]))
    if r.get("places"):
        out.append('<span class="ev__rel-k">Místa:</span> ' + ", ".join(
            f'<a href="mapa.html#{c["id"]}">{html.escape(c["name"])}</a>' for c in r["places"]))
    return f'<p class="ev__rel">{" · ".join(out)}</p>' if out else ""


def event_list(c):
    lis = []
    for r in c["events"]:
        txt = inline_md(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", r["text"]))
        lis.append(f'<li><a href="osa.html#{r["id"]}"><time datetime="{iso(r)}">{human_date(r)}</time></a> {txt}</li>')
    n = len(lis)
    if not n:
        return '<p class="card__none">V časové ose zatím žádný záznam.</p>'
    word = "záznam" if n == 1 else "záznamy" if n < 5 else "záznamů"
    return f'<details class="card__events"><summary>V časové ose: {n} {word}</summary><ol>{"".join(lis)}</ol></details>'


def card_html(c, kind):
    line = c.get("proud", "kontext")
    meta = []
    if c.get("přezdívka"):
        meta.append(f'„{html.escape(c["přezdívka"])}“')
    if c.get("období"):
        meta.append(html.escape(c["období"]))
    if kind == "place" and c.get("přesnost"):
        meta.append("poloha: " + html.escape(c["přesnost"]))
    role = c.get("role") or c.get("typ", "")
    return (f'<article class="card" id="{c["id"]}" data-l="{line}">'
            f'<p class="card__kicker"><span class="dot" data-l="{line}" aria-hidden="true"></span>{LINES.get(line, line)}'
            f'{" · " + html.escape(role) if role else ""}</p>'
            f'<h2 class="card__name">{html.escape(c["name"])}</h2>'
            f'<p class="card__meta">{" · ".join(meta)}</p>'
            f'<p class="card__desc">{inline_md(c.get("popis", ""))}</p>{event_list(c)}</article>')


def render_page(tpl, header, css, robots_meta, base, title, desc, lead, main, foot, script="", extra=""):
    return (tpl.replace("{{ROBOTS}}", robots_meta).replace("{{TITLE}}", html.escape(title))
            .replace("{{DESC}}", html.escape(desc)).replace("{{LEAD}}", lead)
            .replace("{{EXTRA_HEAD}}", extra).replace("{{CSS}}", css).replace("{{HEADER}}", header)
            .replace("{{MAIN}}", main).replace("{{FOOT}}", foot).replace("{{SCRIPT}}", script)
            .replace("{{BASE}}", base).replace("{{DATE}}", datetime.date.today().strftime("%-d. %-m. %Y")))


def picture(fe, name, sizes, cls="", lazy=True, base=""):
    im = fe["images"][name]
    load = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return (f'<img class="{cls}" src="{base}img/{name}-1400.webp" '
            f'srcset="{base}img/{name}-700.webp 700w, {base}img/{name}-1400.webp 1400w" sizes="{sizes}" '
            f'width="{im["w"]}" height="{im["h"]}" alt="{html.escape(im["alt"])}"{load}>')


def extras(f):
    out = ""
    if f.get("program"):
        items = "".join(f"<li>{html.escape(i)}</li>" for i in f["program"])
        out += (f'<div class="feat__prog"><p class="feat__prog-h">{html.escape(f.get("program_title", "Program"))}</p>'
                f'<ol>{items}</ol></div>')
    if f.get("quote"):
        out += (f'<blockquote class="feat__quote"><p>„{html.escape(f["quote"])}“</p>'
                f'<footer>{html.escape(f.get("quote_src", ""))}</footer></blockquote>')
    return out


def short_text(t, n=190):
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"❓.*$", "", t).strip()
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0].rstrip(",;:–- ")
    return cut + "…"


def short_src(source):
    m = re.search(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", source)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", source)
    name = re.split(r"[,(·]", plain)[0].strip()
    if len(name) > 40:
        name = name[:38].rsplit(" ", 1)[0] + "…"
    if m:
        return f'<a href="{html.escape(m.group(2))}" rel="noopener" target="_blank">{html.escape(name)}</a>'
    return html.escape(name)


def feature_for(r, fe):
    f = fe["features"].get(r["date"])
    if f and (not f.get("match") or f["match"] in r["text"]):
        return f
    return None


PREC = {"událost": "událost", "tisk": "zpráva v tisku", "rok": "rok"}


def src_button(source):
    m = re.search(r"\]\((https?://[^)\s]+)\)", source)
    if not m:
        return ""
    url = m.group(1)
    if "kramerius" in url or "ceskadigitalniknihovna" in url:
        label = "Zdroj v Krameriu"
    elif "ndk.cz" in url:
        label = "Zdroj v NDK"
    elif "mzk.cz" in url:
        label = "Zdroj v MZK"
    else:
        label = "Otevřít zdroj"
    return f'<a class="btn-src" href="{html.escape(url)}" rel="noopener" target="_blank">{label}</a>'


def render_event(r, fe, side, base):
    vkey, vlabel = VERIFY.get(r["verify"], ("neovereno", "Neověřeno"))
    tags = [f'<span class="tag tag--{vkey}"><svg aria-hidden="true"><use href="#i-{vkey}"/></svg>{vlabel}</span>']
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
    dot = f'<span class="dot" data-l="{r["line"]}" aria-hidden="true"></span>'
    f = feature_for(r, fe)
    if f:
        fig = ""
        if f.get("img"):
            fig = (f'<figure class="feat__fig">{picture(fe, f["img"], "(min-width: 900px) 540px, 100vw", base=base)}'
                   f'<figcaption>{html.escape(fe["images"][f["img"]].get("credit", fe["credit"]))}</figcaption></figure>')
        cls = "feat" + (" feat--img" if fig else " feat--text") + (" feat--rev" if side else "")
        return (f'<li id="{r["id"]}" class="ev ev--{r["precision"]} {cls}" {attrs}>{fig}<div class="feat__body">'
                f'<p class="feat__kicker" data-l="{r["line"]}">{dot}{LINES[r["line"]]} · {PREC.get(r["precision"], r["precision"])}</p>'
                f'<h3 class="feat__date"><time datetime="{iso(r)}">{when}</time></h3>'
                f'<p class="ev__text">{inline_md(r["text"])}</p>{extras(f)}'
                f'<p class="feat__actions">{src_button(r["source"])}{"".join(tags)}</p>'
                f'<p class="ev__src"><span>Zdroj:</span> {inline_md(r["source"])}</p>{chips(r)}</div></li>')
    return (f'<li id="{r["id"]}" class="ev ev--{r["precision"]}" {attrs}>'
            f'<p class="ev__meta">{dot}<time datetime="{iso(r)}">{when}</time>{when_note}</p>'
            f'<div class="ev__main"><p class="ev__text">{inline_md(r["text"])}</p>'
            f'<p class="ev__tags">{"".join(tags)}</p>{chips(r)}</div>'
            f'<p class="ev__src">{inline_md(r["source"])}</p></li>')


def build(data, out, robots, production, base="", people_path=None, places_path=None):
    rows = parse(data)
    people = parse_cards(people_path or ROOT / "data" / "osobnosti.md")
    places = parse_cards(places_path or ROOT / "data" / "mista.md")
    link_cards(rows, people, places)
    fe = json.loads((ROOT / "src" / "featured.json").read_text(encoding="utf-8"))
    chapters = fe["chapters"]
    years = {}
    for r in rows:
        years.setdefault(r["date"][:4], []).append(r)

    year_nav = "".join(f'<li data-y="{y}"><a href="#r{y}">{y}</a></li>' for y in years)
    periods = fe.get("periods", [])
    def pyears(p):
        return [y for y in years if p["from"] <= int(y) <= p["to"]]
    def bubble(p, href):
        dark = " bubble--dark" if p.get("dark") else ""
        lab = f'{p["from"]}–{str(p["to"])[2:]}'
        return (f'<li data-p="{p["from"]}"><a class="bubble{dark}" href="{href}">'
                f'<span class="bubble__y">{lab}</span><span class="bubble__l">{html.escape(p["label"])}</span></a></li>')
    period_nav_home = "".join(bubble(p, f'#p{p["from"]}') for p in periods if pyears(p))
    period_nav_osa = "".join(bubble(p, f'#r{pyears(p)[0]}') for p in periods if pyears(p))
    by_date = {}
    for r in rows:
        by_date.setdefault(r["date"], r)
    blocks = []
    for i, p in enumerate(periods):
        ys = pyears(p)
        if not ys:
            continue
        r = by_date.get(p["date"])
        if not r:
            raise SystemExit(f"Období {p['from']}: řádek s datem {p['date']} v ose není.")
        n = sum(len(years[y]) for y in ys)
        fig = ""
        if p.get("img"):
            im = fe["images"][p["img"]]
            fig = (f'<figure class="period__fig">{picture(fe, p["img"], "(min-width: 900px) 540px, 100vw", base=base)}'
                   f'<figcaption>{html.escape(im.get("credit", fe["credit"]))}</figcaption></figure>')
        f = feature_for(r, fe) or {}
        cls = "period" + (" period--dark" if p.get("dark") else "") + (" period--rev" if i % 2 else "") + ("" if fig else " period--text") + (" period--portrait" if p.get("portrait") else "")
        pool = [x for y in ys for x in years[y] if x is not r]
        def score(x):
            v = VERIFY.get(x["verify"], ("neovereno",))[0]
            return ((3 if feature_for(x, fe) else 0) + (2 if v == "overeno" else 0)
                    + (1 if x["precision"] == "událost" else 0) + (1 if x["line"] != "kontext" else 0))
        if p.get("more"):
            picks = [by_date[d] for d in p["more"] if d in by_date]
        else:
            ranked = sorted(pool, key=lambda x: (-score(x), x["date"]))
            picks = []
            while len(picks) < 4 and len(picks) < len(ranked):
                used = {x["line"] for x in picks}
                nxt = next((x for x in ranked if x not in picks and x["line"] not in used), None) \
                    or next(x for x in ranked if x not in picks)
                picks.append(nxt)
                if len({x["line"] for x in picks}) == len({x["line"] for x in ranked}):
                    used = set()
            picks.sort(key=lambda x: x["date"])
        rows_html = "".join(
            f'<li class="prow" data-l="{x["line"]}"><a class="prow__d" href="osa.html#{x["id"]}">'
            f'<span class="dot" data-l="{x["line"]}" aria-hidden="true"></span><time datetime="{iso(x)}">{human_date(x)}</time></a>'
            f'<span class="prow__t">{html.escape(short_text(x["text"]))}</span><span class="prow__s">{short_src(x["source"])}</span></li>'
            for x in picks)
        more_html = (f'<section class="period__list" aria-label="Další záznamy {p["from"]}–{p["to"]}">'
                     f'<h3 class="period__list-h">Další záznamy {p["from"]}–{p["to"]}</h3><ul>{rows_html}</ul>'
                     f'</section>') if picks else ""
        blocks.append(
            f'<div class="period-wrap">'
            f'<article class="{cls}" id="p{p["from"]}" aria-labelledby="ph{p["from"]}">{fig}<div class="period__body">'
            f'<p class="period__kicker">{p["from"]}–{p["to"]} · {html.escape(p["title"])}</p>'
            f'<h2 class="period__date" id="ph{p["from"]}"><time datetime="{iso(r)}">{human_date(r)}</time></h2>'
            f'<p class="period__text">{inline_md(p.get("text") or r["text"])}</p>{extras(f) if p.get("extras") else ""}'
            f'<p class="period__actions">{src_button(r["source"])}'
            f'<a class="period__more" href="osa.html#r{ys[0]}">Celé období na časové ose ({n} záznamů)</a></p>'
            f'</div></article>{more_html}</div>')
    periods_html = "\n".join(blocks)
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
        f'<button type="button" class="fbtn fbtn--org" data-group="l" data-key="{k}" data-l="{k}" aria-pressed="false">'
        f'<span class="dot" data-l="{k}" aria-hidden="true"></span>{v}</button>'
        for k, v in SHORT.items())
    verify_buttons = "".join(
        f'<button type="button" class="fbtn" data-group="v" data-key="{k}" aria-pressed="true">{v}</button>'
        for k, v in (("overeno", "Ověřeno"), ("dp", "Z DP 2021"), ("neovereno", "Neověřeno")))

    tpl = (ROOT / "src" / "osa.html").read_text(encoding="utf-8")
    logo = (ROOT / "src" / "logo.svg.html").read_text(encoding="utf-8")
    header_tpl = (ROOT / "src" / "header.html").read_text(encoding="utf-8").replace("{{LOGO}}", logo).replace("{{BASE_PAGE}}", "")

    def header(cur):
        h = header_tpl
        for k in ("OSA", "OSOBY", "MAPA", "ZDROJE"):
            h = h.replace("{{CUR_%s}}" % k, ' aria-current="page"' if k == cur else "")
        return h
    css = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "src" / "app.js").read_text(encoding="utf-8")
    robots_meta = "" if production else '<meta name="robots" content="noindex, nofollow">\n'

    def fill(t, cur, nav):
        return (t
            .replace("{{ROBOTS}}", robots_meta)
            .replace("{{HEADER}}", header(cur))
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
            .replace("{{CHAPTER_NAV}}", nav).replace("{{PERIOD_NAV}}", period_nav_home).replace("{{PERIODS}}", periods_html)
            .replace("{{HERO_IMG}}", hero_html)
            .replace("{{CREDIT}}", html.escape(fe["credit"]))
            .replace("{{BASE}}", base)
            .replace("{{YEARS}}", str(int(last) - int(first) + 1))
            .replace("{{LINE_BUTTONS}}", line_buttons)
            .replace("{{VERIFY_BUTTONS}}", verify_buttons)
            .replace("{{SECTIONS}}", sections)
            .replace("{{DATE}}", datetime.date.today().strftime("%-d. %-m. %Y")))
    page = fill(tpl, "OSA", period_nav_osa)
    home = fill((ROOT / "src" / "home.html").read_text(encoding="utf-8"), "HOME", "")
    era_tiles = []
    for i, er in enumerate(fe.get("eras", []), 1):
        yrs = f'{er["from"]}–{er["to"]}'
        if er.get("href"):
            img = picture(fe, er["img"], "(min-width: 900px) 360px, 100vw", base=base) if er.get("img") else ""
            era_tiles.append(f'<li class="era era--open"><a href="{er["href"]}">{img}<span class="era__body">'
                             f'<span class="era__n">{i}. epocha</span><span class="era__y">{yrs}</span>'
                             f'<span class="era__t">{html.escape(er["title"])}</span><span class="era__l">{html.escape(er["lead"])}</span>'
                             f'<span class="era__go">Otevřít epochu</span></span></a></li>')
        else:
            era_tiles.append(f'<li class="era era--soon"><span class="era__body"><span class="era__n">{i}. epocha</span>'
                             f'<span class="era__y">{yrs}</span><span class="era__t">{html.escape(er["title"])}</span>'
                             f'<span class="era__l">{html.escape(er["lead"])}</span><span class="era__tag">Připravujeme</span></span></li>')
    epochy = fill((ROOT / "src" / "epochy.html").read_text(encoding="utf-8"), "HOME", "").replace("{{ERAS}}", "".join(era_tiles))
    if "{{" in page or "{{" in home or "{{" in epochy:
        raise SystemExit("V šabloně zůstal nenahrazený zástupný text.")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(epochy, encoding="utf-8")
    (out.parent / "epocha-1911-1945.html").write_text(home, encoding="utf-8")
    (out.parent / "osa.html").write_text(page, encoding="utf-8")
    if not base:
        for d in ("img", "fonts"):
            shutil.copytree(ROOT / "src" / d, out.parent / d, dirs_exist_ok=True)
    page_tpl = (ROOT / "src" / "page.html").read_text(encoding="utf-8")
    groups = [(k, v) for k, v in LINES.items() if any(c.get("proud") == k for c in people)]
    people_main = "".join(
        f'<section class="cards-sec"><h2 class="cards-sec__h">{v}</h2><div class="cards">'
        + "".join(card_html(c, "person") for c in people if c.get("proud") == k) + '</div></section>'
        for k, v in groups)
    (out.parent / "osobnosti.html").write_text(render_page(
        page_tpl, header("OSOBY"), css, robots_meta, base, "Osobnosti",
        "Karty lidí, kteří vedli skauting v Liberci od roku 1911: Pfadfinder, junáci, skautky a židovští skauti.",
        f"{len(people)} lidí, kteří liberecký skauting zakládali a vedli. U každého je přehled záznamů z časové osy, ve kterých se objevuje. Popisy vycházejí jen z osy a průběžně se doplňují.",
        people_main, "Popisy označené 🤖 sepsal Claude z časové osy, čekají na kontrolu."), encoding="utf-8")

    mapped = [c for c in places if c.get("souřadnice")]
    unmapped = [c for c in places if not c.get("souřadnice")]
    pts = [dict(id=c["id"], name=c["name"], l=c.get("proud", "kontext"), typ=c.get("typ", ""),
                lat=float(c["souřadnice"].split(",")[0]), lon=float(c["souřadnice"].split(",")[1]),
                approx=c.get("přesnost", "").startswith(("přibližně", "neurčeno")), n=len(c["events"])) for c in mapped]
    places_main = ('<div id="map" class="map" role="region" aria-label="Mapa míst"></div>'
                   '<p class="map__note">Plný bod = místo známe přesně nebo aspoň obec; kroužek = poloha je přibližná. Kliknutím na bod se dostanete na kartu místa.</p>'
                   f'<section class="cards-sec"><h2 class="cards-sec__h">Místa na mapě ({len(mapped)})</h2><div class="cards">'
                   + "".join(card_html(c, "place") for c in mapped) + '</div></section>'
                   + (f'<section class="cards-sec"><h2 class="cards-sec__h">Zatím bez polohy ({len(unmapped)})</h2><div class="cards">'
                      + "".join(card_html(c, "place") for c in unmapped) + '</div></section>' if unmapped else ""))
    leaflet_css = (ROOT / "src" / "vendor" / "leaflet" / "leaflet.css").read_text(encoding="utf-8")
    leaflet_js = (ROOT / "src" / "vendor" / "leaflet" / "leaflet.js").read_text(encoding="utf-8")
    map_js = (ROOT / "src" / "map.js").read_text(encoding="utf-8")
    script = (f"<script>{leaflet_js}</script>\n<script>var PLACES = {json.dumps(pts, ensure_ascii=False)};\n{map_js}</script>")
    (out.parent / "mapa.html").write_text(render_page(
        page_tpl, header("MAPA"), css, robots_meta, base, "Mapa míst",
        "Mapa míst libereckého skautingu od roku 1911: heimy, klubovny, tábořiště, srazy a výlety.",
        f"Heimy, klubovny, tábořiště, srazy a výlety ze záznamů časové osy – {len(places)} míst, {len(mapped)} z nich na mapě.",
        places_main, "Mapové podklady © přispěvatelé OpenStreetMap (ODbL). Knihovna Leaflet (BSD-2).",
        script, f"<style>{leaflet_css}</style>\n"), encoding="utf-8")

    plain_src = [re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", r["source"]) for r in rows]
    src_secs = []
    for sec in fe.get("sources", []):
        items = []
        for it in sec["items"]:
            n = sum(1 for ps in plain_src if re.search(it["key"], ps))
            q = it.get("q") or re.sub(r"[\\^$()]", "", it["key"].split("|")[0]).strip()
            where = it.get("where", "")
            if it.get("url"):
                where = f'<a href="{html.escape(it["url"])}" rel="noopener" target="_blank">{html.escape(where or "otevřít")}</a>'
            else:
                where = html.escape(where)
            cnt = (f'<a class="src__n" href="osa.html?q={html.escape(q)}">{n}&times; v ose</a>' if n else "")
            items.append(f'<li class="src"><p class="src__name">{html.escape(it["n"])}</p>'
                         + (f'<p class="src__d">{html.escape(it["d"])}</p>' if it.get("d") else "")
                         + f'<p class="src__meta">{where}{" · " if where and cnt else ""}{cnt}</p></li>')
        src_secs.append(f'<section class="cards-sec"><h2 class="cards-sec__h">{html.escape(sec["h"])}</h2>'
                        + (f'<p class="src__lead">{html.escape(sec["lead"])}</p>' if sec.get("lead") else "")
                        + f'<ul class="srcs">{"".join(items)}</ul></section>')
    (out.parent / "zdroje.html").write_text(render_page(
        page_tpl, header("ZDROJE"), css, robots_meta, base, "Zdroje",
        "Prameny a literatura k časové ose skautingu v Liberci 1912–1940: dobový tisk, skautské časopisy, almanachy, kroniky a odborné práce.",
        "Z čeho časová osa vychází. U každého pramene je, kde se dá najít, a kolikrát se v ose objevuje – kliknutím se zobrazí příslušné záznamy.",
        "".join(src_secs), "Seznam se doplňuje s každým novým pramenem."), encoding="utf-8")

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
    ap.add_argument("--people", default=None, help="soubor s kartami osobností (výchozí data/osobnosti.md)")
    ap.add_argument("--places", default=None, help="soubor s místy (výchozí data/mista.md)")
    a = ap.parse_args()
    build(a.data, a.out, not a.no_robots, os.environ.get("PRODUCTION") == "1", a.asset_base, a.people, a.places)
