# Website SEO Automations

An AI-powered SEO agent workspace. Drop a URL, get a full audit — technical, on-page, keyword gaps, backlinks, AND AI search (GEO) — with copy-paste ready fixes. No dashboards, no manual copy-paste.

---

## How It Works

This project connects your AI agent (Claude / Antigravity) directly to live SEO data via **OpenSEO MCP → DataForSEO API**.

```
You type:  "audit alephindia.in"
     ↓
Agent fetches live data via OpenSEO MCP (no copy-paste needed)
     ↓
Full audit: traffic, keywords, backlinks, technical errors, GEO check
     ↓
Report saved to: audits/alephindia.in-[date].md
```

---

## Setup (One-Time)

### Step 1 — Get Free DataForSEO Credits
1. Go to [dataforseo.com](https://dataforseo.com)
2. Sign up (no credit card required)
3. You get **$1 free credit** (~10–15 full website audits)

### Step 2 — Connect OpenSEO
1. Go to [openseo.so](https://openseo.so)
2. Sign up (no credit card, **$0.50 free trial**)
3. Enter your DataForSEO API login+password in OpenSEO settings

### Step 3 — Open This Project in Antigravity / Claude Code
- The `.mcp.json` file in this folder automatically connects OpenSEO
- Set `D:\Projects\website-seo-automations` as your active workspace

### Step 4 — Authorize Once
First time you use an OpenSEO tool, it will prompt you to log in via browser. Do that once and you're permanently connected.

---

## Commands

| Say This | What Happens |
|---|---|
| `audit [url]` | Full 5-phase SEO + GEO audit |
| `compare [url1] vs [url2]` | Side-by-side audit + keyword gap report |
| `who ranks for [keyword]` | SERP analysis for any keyword |
| `fix my title and description for [url]` | Rewritten meta tags, ready to paste |
| `generate schema for [url]` | Full JSON-LD schema markup |
| `generate llms.txt for [url]` | GEO-ready llms.txt file |
| `check if [url] is in AI search` | GEO-only audit |
| `find backlink opportunities for [url]` | Competitor backlinks you don't have yet |

---

## Project Structure

```
website-seo-automations/
├── AGENTS.md          ← Agent brain (do not delete)
├── .mcp.json          ← MCP server connection (do not delete)
├── README.md          ← This file
├── audits/            ← Saved audit reports (auto-generated)
└── reports/           ← Custom reports and comparisons
```

---

## Free Credit Estimate

| DataForSEO Task | Cost | How Many on $1 Free |
|---|---|---|
| Domain overview | ~$0.01 | 100x |
| Top 50 keywords | ~$0.05 | 20x |
| Top 100 backlinks | ~$0.001 | 1000x |
| Site audit (50 pages) | ~$0.10 | 10x |
| **Full competitor audit** | **~$0.15** | **~8–10 audits free** |

After free credits: minimum $50 top-up (pay-as-you-go, no subscription).
