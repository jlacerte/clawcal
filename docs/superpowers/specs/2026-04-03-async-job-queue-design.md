# Async Job Queue — Design Spec

## Problème

Le `code_agent` MCP tool actuel est synchrone : Claude Code attend que `Agent.run()` finisse, mais le timeout MCP (~120s) coupe la connexion avant que le modèle local (qwen3:14b) termine. Résultat : le tool est inutilisable pour des tâches non-triviales.

## Solution

Transformer l'interaction en 3 tools async (submit / status / result) avec exécution en background. Chaque appel MCP est instantané — zéro timeout.

## Nouveaux tools MCP

### `code_agent_submit`

Lance une tâche en background, retour immédiat.

```
Input:  { prompt: str, working_directory?: str, max_iterations?: int }
Output: { task_id: str, status: "running" }
```

### `code_agent_status`

Vérifie l'état d'une tâche. Instantané.

```
Input:  { task_id: str }
Output: { task_id: str, status: "running"|"done"|"error", elapsed_seconds: float, iterations: int }
```

### `code_agent_result`

Récupère le résultat d'une tâche terminée.

```
Input:  { task_id: str }
Output (done):    { task_id: str, status: "done", result: str, elapsed_seconds: float }
Output (running): { task_id: str, status: "running", message: "Pas encore terminé" }
Output (error):   { task_id: str, status: "error", error: str, elapsed_seconds: float }
```

## Architecture

### TaskManager (`src/task_manager.py`) — nouveau fichier

Classe qui gère le cycle de vie des tâches async.

**Stockage en mémoire :**

```python
tasks: dict[str, TaskEntry] = {
    "abc123": {
        "task_id": "abc123",
        "status": "running",         # running | done | error
        "prompt": "...",
        "result": None,              # str quand done
        "error": None,               # str quand error
        "started_at": float,         # time.monotonic()
        "finished_at": None,         # float quand terminé
        "iterations": 0,
        "asyncio_task": Task,        # référence asyncio
    }
}
```

**Méthodes :**

- `submit(prompt, working_directory, max_iterations) -> dict` — crée l'entrée, lance `asyncio.create_task()`, retourne task_id
- `status(task_id) -> dict` — lecture du dict, retourne l'état
- `result(task_id) -> dict` — retourne le résultat si done, sinon le status actuel
- `_run_agent(task_id, prompt, ...) -> None` — coroutine interne, appelle `Agent.run()`, met à jour l'entrée

**Contraintes :**

- Exécution séquentielle via `asyncio.Lock` (un seul agent à la fois) — même contrainte que le `code_agent` actuel
- Pas de persistence — les tâches vivent en mémoire, perdues au redémarrage du service

### Signaux fichier

Quand une tâche termine, écriture d'un fichier signal :

- Succès : `~/.clawcal/signals/{task_id}.done` — contient le résultat
- Erreur : `~/.clawcal/signals/{task_id}.error` — contient le message d'erreur

Le dossier `~/.clawcal/signals/` est créé au démarrage si absent.

### Modifications à `server.py`

- Instancier `TaskManager` au démarrage (réutilise `LlmClient`, `ToolRegistry`, `CostEstimator` existants)
- Ajouter les 3 tools dans `@server.list_tools()`
- Router les appels dans `@server.call_tool()`
- Le `code_agent` synchrone reste inchangé pour compatibilité

## Fichiers touchés

| Fichier | Action |
|---------|--------|
| `src/task_manager.py` | Nouveau — classe TaskManager |
| `src/server.py` | Modifier — 3 nouveaux tools + instanciation TaskManager |
| `src/agent.py` | Aucun changement |
| `tests/test_task_manager.py` | Nouveau — tests unitaires |

## Flow typique Claude <-> Clawcal

```
Justin:  "Crée-moi un script qui parse du JSON"
Claude:  -> code_agent_submit(prompt="...")
Clawcal: -> { task_id: "x7f", status: "running" }
Claude:  "Clawcal travaille dessus..."
Claude:  -> code_agent_status(task_id="x7f")
Clawcal: -> { status: "running", elapsed: 30, iterations: 2 }
Claude:  -> code_agent_status(task_id="x7f")
Clawcal: -> { status: "done", elapsed: 95 }
Claude:  -> code_agent_result(task_id="x7f")
Clawcal: -> { result: "Script créé à /tmp/parse.py..." }
Claude:  *review le code, donne le résultat à Justin*
```

## Hors scope (v1)

- Persistence SQLite des tâches
- Cancel d'une tâche en cours
- Tâches parallèles (la lock force le séquentiel)
- Streaming du output en temps réel
- Mode ping-pong / spécialisation (features futures)
