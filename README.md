# Piper

Daily aggregator of classic Piper taildragger classified listings (J-3
Cub, J-5 Cub Cruiser, L-4 Cub, PA-11 Cub Special, PA-15/PA-17 Vagabond,
PA-16 Clipper, PA-18 Super Cub, PA-20 Pacer) from
[Barnstormers.com](https://www.barnstormers.com), published as a static
page (`docs/index.html`) meant to be embedded via `<iframe>` on
taildraggers.com.

Controller.com was evaluated (in the companion [Aeronca](https://github.com/taildraggers/aeronca)
repo) and dropped: its search results are only reachable through an internal
client-side widget (not a plain URL), which a headless browser can't drive
reliably for an unattended daily job.

## Categories scraped

This pulls directly from eleven Barnstormers category pages - nine of them
dedicated single-model pages, plus two broader Piper taildragger hubs:

- [J-3 Cub](https://www.barnstormers.com/category-21182-Piper--J-3-Cub.html)
- [J-5 Cub Cruiser](https://www.barnstormers.com/category-21184-Piper--J-5-Cub-Cruiser.html)
- [L-4 Cub](https://www.barnstormers.com/category-21185-Piper--L--4-Cub.html)
- [PA-11 Cub Special](https://www.barnstormers.com/category-21190-Piper--PA-11-Cub-Special.html)
- [PA-15 Vagabond](https://www.barnstormers.com/category-21193-Piper--PA-15-Vagabond.html)
- [PA-16 Clipper](https://www.barnstormers.com/category-21194-Piper--PA-16-Clipper.html)
- [PA-17 Vagabond](https://www.barnstormers.com/category-21195-Piper--PA-17-Vagabond.html)
- [PA-18 Super Cub](https://www.barnstormers.com/category-21196-Piper--PA-18-Super-Cub.html)
- [PA-20 Pacer](https://www.barnstormers.com/category-21197-Piper--PA-20-Pacer.html)
- [Super Cub (general)](https://www.barnstormers.com/category-21249-Piper--Super-Cub.html)
- [Taildragger (general)](https://www.barnstormers.com/category-21250-Piper--Taildragger.html)

Edit `CATEGORY_URLS` in `scraper/barnstormers.py` to change this list.

Because most of these are dedicated model categories rather than a broad
hub, no brand *allowlist* is applied on top - that approach was tried in
the Cessna repo and turned out to drop lots of genuine, unbranded parts
listings ("185 Horizontal Stab" never mentions "Cessna"). Instead, titles
are only dropped when they name a *different* aircraft manufacturer or an
unrelated item (`OFF_BRAND_PHRASES` in `scraper/barnstormers.py`), the
same approach used in the Cessna repo. The two broader hub pages
("Super-Cub" and "Taildragger") carry more contamination risk than the
nine dedicated pages; if testing turns up systematic off-model leakage
specifically from those two, they can be dropped from `CATEGORY_URLS` or
given a stricter allowlist.

On top of that, only whole-aircraft-for-sale listings are published. Each
ad's title must match a recognized Piper model designator (PA-11 through
PA-20, L-4, J-3, J-5, or a common marketing name like "Super Cub",
"Clipper", or "Pacer" - see `_extract_model` in `scraper/barnstormers.py`);
titles that read as parts, accessories, services, or raffles are dropped.
The Tri-Pacer (PA-22) is deliberately excluded from the "Pacer" name match
since it's a tricycle-gear aircraft, not a taildragger. The PA-15 and
PA-17 Vagabond share the same name and airframe, so a bare "Vagabond"
mention with no PA number is published generically as "Piper Vagabond"
rather than guessed at. Every surviving listing's title is rewritten to a
canonical **`YEAR Piper MODEL`** form when the ad states a model year
(e.g. `1946 Piper J-3`), or just **`Piper MODEL`** when it doesn't - a
missing year isn't disqualifying, since plenty of genuine ads simply don't
state one in the title.

## How it works

- `scraper/barnstormers.py` fetches each of the eleven category pages
  above, follows pagination, and visits every listing's detail page to
  pull out the price, location, and posted date (falling back to regex
  heuristics over the visible text since the site doesn't expose
  structured data). The title is derived from the listing URL's own SEO
  slug, since every detail page shares one generic `<title>`/`<h1>`.
- `main.py` runs the scraper, de-duplicates results, sorts them
  newest-posted-first, and renders them into `docs/index.html` titled
  **"Other Piper Ads on the Web"**, with one row per listing: Title
  (linked to the original ad), Price, Location, Date Posted, and Site
  Posted On. Links use `rel="noopener noreferrer"` and the page sets a
  `no-referrer` meta policy, so Barnstormers never sees that the click
  came from taildraggers.com.
- `.github/workflows/daily-scrape.yml` runs the whole thing once a day (13:00 UTC),
  commits the regenerated `docs/index.html` if it changed, and can also be triggered
  manually from the Actions tab (`workflow_dispatch`).

## One-time setup: enable GitHub Pages

This repo publishes `docs/index.html` as a plain static file — GitHub Pages just needs
to be pointed at it once:

1. Go to **Settings → Pages** in this repository.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`. Save.
4. GitHub will publish the page at `https://taildraggers.github.io/piper/`
   (may take a minute or two the first time).

Also check **Settings → Actions → General**:
- **Actions permissions**: "Allow all actions and reusable workflows".
- **Workflow permissions**: "Read and write permissions" (needed so the daily
  job can commit the regenerated page back to the repo).

## Embedding on taildraggers.com

```html
<iframe
  src="https://taildraggers.github.io/piper/"
  title="Other Piper Ads on the Web"
  style="width: 100%; height: 800px; border: 0;"
  loading="lazy">
</iframe>
```

## Running locally

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
python main.py
```

This writes/overwrites `docs/index.html`.

## Notes

- If Barnstormers changes its markup or is briefly unreachable, the run logs will
  show a `[warn]`/`[error]` line pointing at what broke rather than failing silently.
- The scraper identifies itself with a browser-like `User-Agent` and adds a short
  delay between requests to be polite to the site.
