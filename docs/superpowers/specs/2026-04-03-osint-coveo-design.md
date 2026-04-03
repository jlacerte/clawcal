# OSINT Competitive Intelligence — Coveo Design Spec

## Objectif

Analyser Coveo (coveo.com) en competitive intelligence : stack technique, positionnement produit, et stratégie de systèmes verticaux d'entreprise. Documenter le processus comme recherche AI sur la collaboration Claude ↔ Clawcal.

## Cible

- **Entreprise :** Coveo Solutions Inc.
- **URL :** https://www.coveo.com/fr
- **Domaine :** AI-powered search, recommendations, personalization
- **Pertinence :** Compétiteur dans l'espace AI enterprise, approche verticale similaire à ce que Tacit-AI veut faire

## Scope de l'analyse

### 1. Stack technique (Clawcal)

Données publiquement observables depuis coveo.com :
- Headers HTTP (server, x-powered-by, CDN, security headers)
- Technologies frontend (frameworks JS, CSS, build tools)
- DNS records (MX, TXT, nameservers)
- Certificats SSL (issuer, validité)
- Meta tags, structured data, Open Graph
- Scripts tiers (analytics, marketing, chat)

### 2. Positionnement produit (Claude)

Extraire et analyser depuis les pages publiques :
- Segments de marché ciblés
- Features principales mises de l'avant
- Messaging et value proposition
- Pricing model (si public)

### 3. Stratégie de verticaux (Claude — focus principal)

Analyser comment Coveo structure son offre par industrie :
- Quels verticaux ils ciblent (retail, manufacturing, services financiers, etc.)
- Comment ils customisent leur messaging par vertical
- Quelles features sont spécifiques à chaque vertical vs horizontales
- Leur approche go-to-market par industrie
- Comparaison avec l'approche que Tacit-AI pourrait adopter

## Architecture du pipeline

```
osint-lab/
├── scripts/
│   ├── tech_recon.py      # Clawcal — headers HTTP, DNS, détection de stack
│   └── page_scraper.py    # Clawcal — scrape les pages solutions/verticaux
├── data/
│   ├── tech_recon.json    # Output du recon technique
│   ├── pages/             # Contenu scrappé des pages
│   └── report.md          # Rapport final
└── research/
    └── collaboration_log.md  # Journal de recherche AI
```

## Répartition des tâches

| # | Tâche | Agent | Justification |
|---|-------|-------|---------------|
| 1 | Tech recon (headers, DNS, technologies) | Clawcal | Fetch HTTP + parsing mécanique |
| 2 | Scrape pages solutions/verticaux | Clawcal | Extraction de texte depuis HTML |
| 3 | Analyse positionnement + verticaux | Claude | Synthèse stratégique, raisonnement complexe |
| 4 | Rapport comparatif vs Tacit-AI | Claude | Jugement business, mise en contexte |

## Journal de recherche AI

Chaque étape documentée dans `collaboration_log.md` avec :
- **Qui** a fait la tâche (Claude ou Clawcal)
- **Temps** d'exécution (elapsed_seconds)
- **Tokens** consommés (via observabilité TaskManager)
- **Qualité** — résultat utilisable tel quel ou correction nécessaire (1-5)
- **Décision** — pourquoi cette tâche a été assignée à cet agent

Tableau récapitulatif à la fin avec conclusions sur la collaboration.

## Scripts

### tech_recon.py

- Fait des requêtes HTTP à coveo.com et pages clés
- Parse les headers de réponse
- Détecte les technologies via patterns connus (meta tags, scripts, headers)
- Fait un lookup DNS (via socket/subprocess dig)
- Écrit les résultats dans `data/tech_recon.json`
- Librairies : uniquement la stdlib Python (urllib, socket, ssl, json, subprocess)
- Pas de dépendances externes à installer

### page_scraper.py

- Fetch les pages solutions/industries de coveo.com
- Extrait le texte principal (titres, paragraphes, listes) en retirant le HTML
- Sauvegarde chaque page dans `data/pages/{slug}.txt`
- URLs cibles : page d'accueil, pages solutions, pages industries/verticaux
- Librairies : stdlib Python (urllib, html.parser)
- Pas de dépendances externes

## Contraintes

- Données publiques uniquement — rien qui requiert authentification
- Respecter robots.txt
- Un seul fetch par URL (pas de crawl récursif)
- Pas de rate limiting agressif — délai de 1s entre les requêtes
- Stdlib Python seulement — pas de pip install sur le serveur clawcal
