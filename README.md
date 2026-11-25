# Skauting v Liberci – časová osa

Pracovní časová osa skautingu v Liberci a okolí (1913–1939). Statický web bez frameworku: Python skript sestaví z tabulky v Markdownu jeden HTML soubor.

## Data

- `data/casova-osa.md` – kopie poznámky „Časová osa – události“ ze Second Brain (`01_PROJEKTY/Skauting v Liberci – historie/`). **Zdrojem pravdy je poznámka v trezoru**; sem se kopíruje před každým pushem.
- Jeden řádek tabulky = jedna událost: `datum | přesnost | linka | událost | zdroj | ověření | DP`. Pravidla zápisu jsou v hlavičce souboru.

## Sestavení

```bash
python3 build.py                 # staging: dist/index.html + robots.txt (noindex)
PRODUCTION=1 python3 build.py    # produkce: bez noindex
python3 build.py --data "Časová osa – události.md" --out "Časová osa.html" --no-robots   # lokální náhled v trezoru
```

Zdrojáky jsou v `src/` (`index.html` šablona, `styles.css`, `app.js`); build je vloží do jednoho souboru a vedle něj zkopíruje `src/img/` (WebP 700 a 1400 px) a `src/fonts/` (Barlow, self-hosted). Milníky s velkým blokem, obrázky a kapitoly (bubliny, tmavé předěly) se nastavují v `src/featured.json` – klíčem je datum řádku z tabulky.

Náhled v trezoru bez kopírování obrázků: `--asset-base https://sonyx9.github.io/skaut-osa/`. Všechny události jsou ve statickém HTML, JavaScript jen filtruje.

## Nasazení

Push do `main` spustí GitHub Actions (`.github/workflows/pages.yml`) → GitHub Pages. Výchozí build je staging s `noindex, nofollow` a `robots.txt Disallow: /`.

Jednorázově v repu: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Licence a atribuce

Ikony: [Lucide](https://lucide.dev) (ISC). Písmo: Barlow a Barlow Condensed (SIL OFL 1.1, `src/fonts/OFL-Barlow.txt`). Kresby a strany kronik: Kronika dívčí družiny Racků, Horní Růžodol – Severočeské muzeum v Liberci (zveřejnění ověřit u muzea).
