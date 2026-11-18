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

## Configuration
Variables d'environnement optionnelles (voir `backend/.env.example`) :
`LABMIND_TESSERACT_CMD`, `LABMIND_OCR_LANG`, `LABMIND_DATA_DIR`, `LABMIND_MAX_UPLOAD_BYTES`,
`LABMIND_OLLAMA_URL`, `LABMIND_LLM_MODEL`.

## Tests et démonstration
    cd backend
    python -m pytest -v
    python scripts\demo_agent_trace.py

## Structure
    backend/app/core/            configuration
    backend/app/extraction/      PDF (texte natif) et OCR Tesseract
    backend/app/identification/  catalogue d'alias, parsing des lignes
    backend/app/validation/      contrôles techniques, comparaison arithmétique à la fourchette du laboratoire
    backend/app/knowledge/       registre des sources, découpage en passages et index FAISS
    backend/app/generation/      client Ollama local, RAG, contrôle d'ancrage et repli neutre
    backend/app/agent/           état, traces, outils, planificateur et boucle avec reprise utilisateur
    backend/app/schemas.py       schémas Pydantic (base du contrat API v1)
    backend/scripts/             outils CLI (indexation, benchmark embeddings, démo agent)
    backend/tests/               tests automatisés (dont garde-fou anti-système-expert)
    knowledge_corpus/            sources officielles, métadonnées et index vectoriel
    docs/api-contract/           contrat API v1 + exemples JSON
    docs/archive/                prototype Colab archivé (lecture seule, non conforme)
    docs/decisions/              décisions techniques

## État du projet (fin de l'Étape 4)
Fait :
- Modularisation de la chaîne extraction -> identification -> validation et contrat API v1 validé.
- Retrait du système expert et verrouillage AST (`test_no_expert_system.py`).
- Pipeline RAG local (FAISS + `multilingual-e5-small` + Ollama `qwen2.5:1.5b` + contrôle d'ancrage + première source `ameli.fr` collectée).
- Véritable agent à outils avec boucle adaptative, traces des décisions et interruption/reprise `waiting_for_user`.

Pas encore fait :
- Catalogue étendu aux 6 catégories (fer, ferritine, HbA1c, foie, rein) + extraction robuste / jeu d'évaluation indépendant (Étape 5).
- API FastAPI complète, file de tâches et persistance SQLite/PostgreSQL (Étapes 6 et 7).
- Génération du rapport PDF final et suppression automatique/manuelle vérifiable (Étapes 8 et 9).

## Dette connue
- Le catalogue d'identification ne couvre encore que les 10 paramètres du prototype (NFS, glycémie, lipides).
- `confidence`, `evidence.page` et `detected_categories` restent à alimenter à l'Étape 5.
- Compléter `knowledge_corpus/sources/` avec des fiches dédiées NFS/hémogramme, bilan martial et hygiène de vie (ANSES).