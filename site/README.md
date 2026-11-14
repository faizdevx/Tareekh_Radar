# Case Clock (तारीख घड़ी): public site

Case Clock is a static, bilingual (English/हिंदी) website. It answers two questions:

- **How long will my case take?** Historical time to decision and outcomes for the same case type in your district.
- **Is my case delayed?** You enter your filing, last-hearing and (optionally) next-hearing dates. The site compares them with similar cases. The calculation runs in your browser, and **your dates are never sent anywhere**.

It also has district report cards: median time to decision, share of cases still undecided after 3 years, pending cases with no listing for over a year, and a table by case type.

## Data
`site/data/` holds **aggregates only**, built from real eCourts records published by the Development Data Lab (Harvard Dataverse `doi:10.7910/DVN/GHLGSW`). There are no individual cases, and groups under 30 cases are suppressed. Time to decision uses Kaplan–Meier, so pending cases count as "not yet decided" instead of being dropped. See the in-site Methodology page and [`../docs/public_site.md`](../docs/public_site.md).

Rebuild the data after extracting more filing years:

```bash
python -m tareekh_radar.cli build-site --extracts data/raw/ddl/all_2010/cases.parquet data/raw/ddl/all_2011/cases.parquet --out site/data
```

## Run locally
The site loads JSON with `fetch`, so it needs a web server (opening the file directly won't work):

```bash
python -m http.server 8611 --directory site
```

Then open http://localhost:8611.

## Test

```bash
node --test site/tests/logic.test.js
```

## Deploy
`.github/workflows/pages.yml` runs the tests and publishes `site/` to GitHub Pages on every push to `main` that touches `site/`. To enable it once: repository **Settings → Pages → Source: GitHub Actions**.

## Artwork
All illustrations are original inline SVG (`js/art.js`).
