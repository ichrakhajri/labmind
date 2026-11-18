# LabMind

Application web **informative** : analyse pédagogique d'un compte rendu d'analyses biologiques (PDF ou image).
LabMind ne pose aucun diagnostic et ne prescrit aucun traitement.

## Prérequis
- Python 3.10+
- Tesseract OCR avec le pack français (`tesseract --list-langs` doit afficher `fra`)
- Ollama (local) avec un modèle léger quantifié (ex. `ollama pull qwen2.5:1.5b`)
- Git

## Installation (Windows, PowerShell)
    cd backend
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

## Lancement de l'API locale (Swagger : http://127.0.0.1:8000/docs)
    cd backend
    uvicorn app.main:app --host 127.0.0.1 --port 8000

## Tests, démo et évaluation
    cd backend
    python -m pytest -v
    python scripts\demo_agent_trace.py
    python scripts\generate_eval_samples.py
    python scripts\run_evaluation.py

## Structure
    backend/app/core/            configuration (variables LABMIND_*)
    backend/app/api/             API FastAPI v1 (routes, gestionnaire de tâches, erreurs)
    backend/app/main.py          point d'entrée uvicorn et branchement RAG au démarrage
    backend/app/extraction/      PDF (texte + tableaux par page) et OCR Tesseract avec confiance
    backend/app/identification/  catalogue 6 catégories (21 paramètres), parsing et normalisation
    backend/app/validation/      contrôles techniques, seuils unilatéraux, calcul de confiance
    backend/app/knowledge/       registre des sources, découpage en passages et index FAISS
    backend/app/generation/      client Ollama local, RAG, contrôle d'ancrage et repli neutre
    backend/app/agent/           état, traces, outils, planificateur et boucle avec reprise utilisateur
    backend/app/evaluation/      métriques séparées (identification, valeur, unité, référence)
    backend/app/schemas.py       schémas Pydantic (base du contrat API v1)
    backend/scripts/             outils CLI (indexation, benchmark, démo agent, évaluation)
    backend/tests/               tests automatisés (dont garde-fou anti-système-expert)
    knowledge_corpus/            sources officielles, métadonnées et index vectoriel
    evaluation/                  documents de test, vérités terrain et rapports d'évaluation
    docs/                        contrat API v1, archive Colab et décisions techniques

## État du projet (fin de l'Étape 6)
Fait :
- Backend modulaire complet couvrant les 6 catégories (21 paramètres), sans système expert.
- RAG local (FAISS + `multilingual-e5-small` + Ollama `qwen2.5:1.5b` + contrôle d'ancrage).
- Agent adaptatif avec traces de décision et boucle `waiting_for_user`.
- `detected_categories`, `evidence.page` et `confidence` calculés et exposés dans `Task`.
- Dispositif d'évaluation séparée par champ dans `evaluation/`.
- API FastAPI v1 complète (`POST /v1/tasks`, `GET`, `POST /answer`, `GET /report.pdf`, `DELETE`, OpenAPI).

Pas encore fait :
- Persistance SQLite et suppression automatique après 1 h (Étape 7).
- Génération du rapport PDF final LabMind avec explications et sources citées (Étape 8).
- Durcissement sécurité avancé, complément du corpus et intégration finale frontend (Étapes 9 à 10).