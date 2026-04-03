# OSINT Coveo — Competitive Intelligence Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 2-script OSINT pipeline to analyze Coveo's tech stack and vertical strategy, executed as a Claude-Clawcal collaboration research exercise.

**Architecture:** Two standalone Python scripts (stdlib only) that Clawcal builds and runs via `code_agent_submit`. Claude reads the output data to produce the strategic analysis and research journal. All artifacts live in `/Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/`.

**Tech Stack:** Python 3.12+ stdlib (urllib, socket, ssl, json, html.parser, subprocess)

**Spec:** `docs/superpowers/specs/2026-04-03-osint-coveo-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `osint-lab/scripts/tech_recon.py` | Create (Clawcal) | HTTP headers, DNS, tech detection → JSON |
| `osint-lab/scripts/page_scraper.py` | Create (Clawcal) | Fetch & extract text from Coveo pages → txt files |
| `osint-lab/data/tech_recon.json` | Generated | Output of tech_recon.py |
| `osint-lab/data/pages/*.txt` | Generated | Output of page_scraper.py |
| `osint-lab/data/report.md` | Create (Claude) | Final competitive intelligence report |
| `osint-lab/research/collaboration_log.md` | Create (Claude) | AI research journal documenting the collaboration |

---

### Task 1: Setup project structure

**Files:**
- Create: `osint-lab/scripts/` directory
- Create: `osint-lab/data/pages/` directory
- Create: `osint-lab/research/` directory
- Create: `osint-lab/research/collaboration_log.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/scripts
mkdir -p /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/pages
mkdir -p /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/research
```

- [ ] **Step 2: Create the collaboration log template**

Create `/Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/research/collaboration_log.md`:

```markdown
# Journal de Recherche AI — Collaboration Claude ↔ Clawcal

**Date:** 2026-04-03
**Projet:** OSINT Competitive Intelligence — Coveo
**Objectif:** Documenter la collaboration entre Claude (Opus 4.6, cloud) et Clawcal (qwen3:14b, local GPU) sur une tâche réelle de competitive intelligence.

---

## Méthodologie

- **Claude (Opus 4.6)** : Coordination, analyse stratégique, rédaction
- **Clawcal (qwen3:14b via Ollama)** : Écriture de scripts, exécution locale, extraction de données
- **Communication** : Async job queue (submit/status/result) via MCP

---

## Log des tâches

| # | Tâche | Agent | Temps (s) | Tokens | Qualité (1-5) | Notes |
|---|-------|-------|-----------|--------|---------------|-------|
| | | | | | | |

---

## Observations

(À remplir au fur et à mesure)

---

## Conclusions

(À remplir à la fin)
```

- [ ] **Step 3: Verify structure**

```bash
find /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab -type f -o -type d | sort
```

Expected: directories scripts/, data/, data/pages/, research/ and the collaboration_log.md file.

---

### Task 2: Tech recon script (Clawcal)

**Délégué à Clawcal via `code_agent_submit`.** Claude ne code pas ce script.

- [ ] **Step 1: Submit task to Clawcal**

Use `code_agent_submit` with this prompt:

```
Create a Python script at /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/scripts/tech_recon.py that analyzes coveo.com.

The script must use ONLY Python stdlib (no pip install). It should:

1. HTTP Analysis:
   - GET https://www.coveo.com/fr with a proper User-Agent header
   - Capture all response headers
   - Detect server, CDN (x-cdn, via, cf-ray), security headers (CSP, HSTS, X-Frame-Options)
   - Follow redirects and note the chain

2. Technology Detection:
   - Parse the HTML for meta tags (generator, framework hints)
   - Find all <script src="..."> URLs and identify known frameworks (react, angular, vue, next.js, gatsby, webpack, etc.)
   - Find all <link rel="stylesheet"> URLs
   - Look for known analytics/marketing scripts (google analytics, gtm, hotjar, segment, hubspot, etc.)
   - Detect structured data (JSON-LD, OpenGraph, Twitter cards)

3. DNS Lookup:
   - Use subprocess to run: dig +short coveo.com A
   - Use subprocess to run: dig +short coveo.com MX
   - Use subprocess to run: dig +short coveo.com TXT
   - Use subprocess to run: dig +short coveo.com NS

4. SSL Certificate:
   - Connect to coveo.com:443 with ssl module
   - Extract issuer, subject, expiry date

5. Output:
   - Write all results to /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/tech_recon.json as a structured JSON with sections: http_headers, technologies, dns, ssl, scripts_detected, meta_tags
   - Print a human-readable summary to stdout

6. Constraints:
   - Set User-Agent to "Mozilla/5.0 (compatible; research-bot)"
   - Add 1 second delay between requests
   - Handle errors gracefully (if DNS fails, still continue with HTTP)
   - Use urllib.request, not requests

Run the script after creating it and show the output.
```

- [ ] **Step 2: Monitor task status**

Poll `code_agent_status` until done. Record elapsed_seconds.

- [ ] **Step 3: Retrieve result**

Use `code_agent_result` to get the output. Record quality assessment.

- [ ] **Step 4: Verify output file**

```bash
cat /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/tech_recon.json | python3 -m json.tool | head -50
```

Verify JSON is valid and contains the expected sections.

- [ ] **Step 5: Log in collaboration journal**

Update `research/collaboration_log.md` with Task 2 metrics: agent, time, tokens, quality score, notes.

---

### Task 3: Page scraper script (Clawcal)

**Délégué à Clawcal via `code_agent_submit`.** Claude ne code pas ce script.

- [ ] **Step 1: Submit task to Clawcal**

Use `code_agent_submit` with this prompt:

```
Create a Python script at /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/scripts/page_scraper.py that scrapes key pages from coveo.com.

The script must use ONLY Python stdlib (no pip install). It should:

1. Define these target URLs to scrape:
   - https://www.coveo.com/fr (homepage)
   - https://www.coveo.com/fr/solutions (solutions overview)
   - https://www.coveo.com/fr/solutions/commerce (commerce/retail vertical)
   - https://www.coveo.com/fr/solutions/service (customer service vertical)
   - https://www.coveo.com/fr/solutions/website (website search)
   - https://www.coveo.com/fr/industries (industries overview if it exists)
   - https://www.coveo.com/fr/products (products overview)
   - https://www.coveo.com/fr/platform (platform overview)

2. For each URL:
   - Fetch with urllib.request and a proper User-Agent "Mozilla/5.0 (compatible; research-bot)"
   - If a page returns 404, log it and skip
   - Parse the HTML to extract text content:
     * Page title (<title>)
     * All headings (h1, h2, h3) with their hierarchy
     * Main body text from <p>, <li> tags
     * Any "hero" or prominent text sections
   - Strip all HTML tags, normalize whitespace
   - Save to /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/pages/{slug}.txt
     where slug is derived from the URL path (e.g., "solutions-commerce.txt", "homepage.txt")

3. Use html.parser.HTMLParser to parse HTML (no BeautifulSoup).

4. Add a 1-second delay between requests using time.sleep(1).

5. At the end, print a summary of:
   - How many pages were fetched successfully
   - How many returned 404 or errors
   - List of files created with their sizes

Run the script after creating it and show the output.
```

- [ ] **Step 2: Monitor task status**

Poll `code_agent_status` until done. Record elapsed_seconds.

- [ ] **Step 3: Retrieve result**

Use `code_agent_result` to get the output.

- [ ] **Step 4: Verify output files**

```bash
ls -la /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/pages/
head -30 /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/pages/homepage.txt
```

Verify text files exist and contain meaningful content.

- [ ] **Step 5: Log in collaboration journal**

Update `research/collaboration_log.md` with Task 3 metrics.

---

### Task 4: Strategic analysis (Claude)

**Claude fait cette tâche directement** en lisant les données collectées.

- [ ] **Step 1: Read tech recon data**

Read `/Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/tech_recon.json` and analyze the technical stack.

- [ ] **Step 2: Read scraped pages**

Read all files in `/Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/pages/` to understand Coveo's positioning and vertical strategy.

- [ ] **Step 3: Write the competitive intelligence report**

Create `/Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab/data/report.md` with these sections:

```markdown
# Competitive Intelligence Report — Coveo

## 1. Stack Technique
- Infrastructure (CDN, hosting, SSL)
- Frontend (frameworks, build tools)
- Analytics & marketing stack
- Security posture

## 2. Positionnement Produit
- Value proposition principale
- Segments de marché ciblés
- Features mises de l'avant
- Messaging et ton

## 3. Stratégie de Verticaux
- Verticaux identifiés
- Customisation par industrie (messaging, features, use cases)
- Approche horizontale vs verticale
- Pages dédiées par segment

## 4. Implications pour Tacit-AI
- Opportunités identifiées
- Différenciation possible
- Approches à considérer pour la stratégie verticale
- Leçons à retenir
```

- [ ] **Step 4: Log in collaboration journal**

Update the collaboration log with this task's details. Note: no elapsed_seconds or tokens for Claude tasks — document the qualitative process.

---

### Task 5: Finalize research journal

- [ ] **Step 1: Complete the collaboration log**

Fill in the metrics table in `research/collaboration_log.md` with all task data.

- [ ] **Step 2: Write observations section**

Document observations about the collaboration:
- What worked well
- What didn't work
- Surprising findings
- Quality comparison between agents

- [ ] **Step 3: Write conclusions section**

Summarize findings:
- Is the Claude-Clawcal collaboration model viable?
- What types of tasks are best suited for each agent?
- Recommendations for future collaboration patterns
- Metrics summary (total time, tokens, quality averages)

- [ ] **Step 4: Commit all artifacts**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/osint-lab
git init
git add .
git commit -m "feat: OSINT Coveo competitive intelligence analysis

Claude-Clawcal collaboration research exercise.
Tech recon + page scraping (Clawcal) + strategic analysis (Claude)."
```
