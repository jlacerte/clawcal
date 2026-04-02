# Clawcal Observability — Design Spec

**Date:** 2026-04-02
**Statut:** Draft
**Plateforme cible:** macOS

## Résumé

Ajouter un module d'observabilité complet à Clawcal : structured logging (JSON + terminal), métriques de consommation (tokens, latence, outils), persistence SQLite, et estimation des coûts cloud évités. Permet de mesurer, analyser, et optimiser l'usage de l'agent local.

## Architecture

Module `src/observability/` avec 5 composants indépendants, intégrés au code existant via un pattern callback optionnel (zéro regression sur les 32 tests existants).

```
agent.run()
    │
    ├── LLM call ──► LlmCallEvent ──► collector.record_llm_call()
    │                                       │
    ├── Tool exec ──► ToolEvent ──► collector.record_tool_call()
    │                                       │
    └── fin ──► collector.finalize() ──► SessionEvent
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                          logger          store           cost_estimator
                        (terminal +     (SQLite)         (prix cloud)
                         JSON file)
```

## Structure des fichiers

```
src/observability/
├── __init__.py          # Exports publics
├── events.py            # Dataclasses d'événements
├── logger.py            # Structured logging (JSON fichier + texte terminal)
├── collector.py         # Collecteur de métriques par session
├── store.py             # SQLite store (persistence + requêtes)
└── cost_estimator.py    # Table de prix configurable + calcul d'économies

tests/
├── test_observability.py  # Tests complets du module
```

## Événements (events.py)

Trois dataclasses frozen :

### LlmCallEvent
Émis après chaque appel à Ollama.
- `timestamp: str` — ISO 8601
- `session_id: str` — UUID de la session
- `model: str` — nom du modèle
- `prompt_tokens: int` — prompt_eval_count d'Ollama
- `completion_tokens: int` — eval_count d'Ollama
- `total_tokens: int` — somme des deux
- `latency_ms: float` — total_duration d'Ollama en ms
- `tokens_per_second: float` — completion_tokens / (latency_ms / 1000)
- `had_tool_calls: bool`

### ToolEvent
Émis après chaque exécution d'outil.
- `timestamp: str`
- `session_id: str`
- `tool_name: str`
- `parameters: dict`
- `duration_ms: float`
- `success: bool`
- `error: str | None`
- `result_length: int` — taille de la réponse en caractères

### SessionEvent
Émis à la fin d'un `agent.run()`.
- `timestamp: str`
- `session_id: str` — UUID
- `prompt: str` — message utilisateur original
- `model: str`
- `total_iterations: int`
- `total_llm_calls: int`
- `total_prompt_tokens: int`
- `total_completion_tokens: int`
- `total_tool_calls: int`
- `tools_used: list[str]` — noms des outils utilisés
- `total_duration_ms: float`
- `estimated_cloud_cost: dict[str, float]` — modèle cloud → coût en $
- `local_cost: float` — toujours 0.0

## Logger (logger.py)

Deux handlers simultanés sur le module `logging` Python standard.

### Terminal (StreamHandler)
- Format texte lisible : `[2026-04-02 14:32:01] LLM qwen3:14b | 342 tok in, 128 tok out | 1.2s`
- Outil : `[2026-04-02 14:32:02] TOOL read_file | 45ms | OK`

### Fichier JSON (FileHandler)
- Fichier : `~/.clawcal/logs/clawcal.jsonl`
- Une ligne JSON par événement, parsable avec `jq`
- Rotation automatique : max 10 MB, 5 fichiers gardés

### Initialisation
`setup_logging(log_dir: str, level: int)` — appelée au démarrage du serveur. Crée le répertoire si nécessaire.

### Niveaux
- `DEBUG` — paramètres d'outils, contenu des messages
- `INFO` — appels LLM, exécutions d'outils, résumés de session
- `WARNING` — timeouts, erreurs d'outils récupérables
- `ERROR` — échecs LLM, erreurs non récupérables

## Collector (collector.py)

`MetricsCollector` — une instance par appel `agent.run()`.

### Interface
- `__init__(session_id: str, prompt: str, model: str)`
- `record_llm_call(event: LlmCallEvent)` — accumule tokens et latence
- `record_tool_call(event: ToolEvent)` — accumule durée et compte
- `finalize() -> SessionEvent` — calcule les totaux, estime les coûts cloud

### Intégration
L'agent reçoit un `collector: MetricsCollector | None = None`. Si absent, l'agent fonctionne exactement comme avant.

## SQLite Store (store.py)

`MetricsStore` — persistence et requêtes sur `~/.clawcal/metrics.db`.

### Tables

**`llm_calls` :**
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id` TEXT
- `timestamp` TEXT
- `model` TEXT
- `prompt_tokens` INTEGER
- `completion_tokens` INTEGER
- `total_tokens` INTEGER
- `latency_ms` REAL
- `tokens_per_second` REAL
- `had_tool_calls` INTEGER (0/1)

**`tool_calls` :**
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id` TEXT
- `timestamp` TEXT
- `tool_name` TEXT
- `parameters` TEXT (JSON)
- `duration_ms` REAL
- `success` INTEGER (0/1)
- `error` TEXT
- `result_length` INTEGER

**`sessions` :**
- `session_id` TEXT PRIMARY KEY
- `timestamp` TEXT
- `prompt` TEXT
- `model` TEXT
- `total_iterations` INTEGER
- `total_llm_calls` INTEGER
- `total_prompt_tokens` INTEGER
- `total_completion_tokens` INTEGER
- `total_tool_calls` INTEGER
- `tools_used` TEXT (JSON array)
- `total_duration_ms` REAL
- `estimated_cloud_cost` TEXT (JSON dict)
- `local_cost` REAL

### Interface
- `async init()` — crée les tables si elles n'existent pas
- `async save_session(session: SessionEvent, llm_events: list[LlmCallEvent], tool_events: list[ToolEvent])` — persiste en une transaction
- `async get_usage_summary(days: int = 7) -> dict` — tokens totaux, nombre de sessions, durée
- `async get_cost_savings(days: int = 7) -> dict` — coût cloud évité
- `async get_tool_stats() -> list[dict]` — top outils, taux de succès, durée moyenne
- `async get_model_stats() -> list[dict]` — usage par modèle
- `async close()` — ferme la connexion

### Dépendance
`aiosqlite` — seul ajout au `pyproject.toml`.

## Cost Estimator (cost_estimator.py)

`CostEstimator` — table de prix configurable.

### Prix par défaut (par million de tokens)
```python
DEFAULT_PRICES = {
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}
```

### Interface
- `__init__(prices: dict | None = None)` — charge depuis `~/.clawcal/prices.json` si existant, sinon défauts
- `estimate(prompt_tokens: int, completion_tokens: int) -> dict[str, float]` — coût par modèle cloud
- `add_model(name: str, input_price: float, output_price: float)` — ajouter/modifier un modèle

## Intégration avec le code existant

### llm_client.py
- Nouveau dataclass `LlmUsage` : `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_ms`, `tokens_per_second`
- `LlmResponse` reçoit un champ optionnel `usage: LlmUsage | None = None`
- `parse_response()` extrait `prompt_eval_count`, `eval_count`, `total_duration` de la réponse Ollama

### agent.py
- Nouveau paramètre `collector: MetricsCollector | None = None`
- Après chaque appel LLM → `collector.record_llm_call()` si collector présent
- Après chaque outil → `collector.record_tool_call()` avec mesure de durée
- En fin de `run()` → `collector.finalize()` et log du SessionEvent

### server.py
- `setup_logging()` au démarrage
- Crée un `MetricsStore` et l'initialise
- Crée un `MetricsCollector` par appel `code_agent`
- Persiste le `SessionEvent` après chaque session

### Principe clé
Tout est optionnel. Si `collector` est `None`, l'agent fonctionne exactement comme avant. Les 32 tests existants passent sans modification.

## Dépendances ajoutées

- `aiosqlite` — SQLite async (seul ajout)
