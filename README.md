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

## Tests
    cd backend
    python -m pytest -v

## Structure
    backend/app/core/            configuration
    backend/app/extraction/      PDF (texte natif) et OCR Tesseract
    backend/app/identification/  catalogue d'alias, parsing des lignes
    backend/app/validation/      contrôles techniques, comparaison arithmétique à la fourchette du laboratoire
    backend/app/knowledge/       registre des sources, découpage en passages et index FAISS
    backend/app/generation/      client Ollama local, RAG, contrôle d'ancrage et repli neutre
    backend/app/schemas.py       schémas Pydantic (base du contrat API v1)
    backend/scripts/             outils CLI (indexation, benchmark embeddings, test RAG local)
    backend/tests/               tests automatisés (dont garde-fou anti-système-expert)
    knowledge_corpus/            sources officielles, métadonnées et index vectoriel
    docs/api-contract/           contrat API v1 + exemples JSON
    docs/archive/                prototype Colab archivé (lecture seule, non conforme)
    docs/decisions/              décisions techniques

## État du projet (fin de l'Étape 3)
Fait :
- Modularisation complète de la chaîne extraction -> identification -> validation.
- Contrat API v1 rédigé et validé avec le frontend (endpoints à venir à l'Étape 6).
- Retrait du système expert et verrouillage AST (`test_no_expert_system.py`).
- Pipeline documentaire (`knowledge_corpus/` + chunker + FAISS + benchmark embeddings CPU).
- Générateur RAG avec client Ollama local, contrôle d'ancrage, reformulation prudente et repli neutre.

Pas encore fait :
- Collecte complète des textes institutionnels réels pour les 6 catégories dans `knowledge_corpus/sources/`.
- Agent à outils avec boucle d'adaptation et confirmation utilisateur `waiting_for_user` (Étape 4).
- Catalogue complet (6 catégories), benchmark OCR, jeu d'évaluation indépendant (Étape 5).
- API FastAPI, base de données SQLite/PostgreSQL, rapport PDF, suppression des données (Étapes 6 à 8).

## Dette connue
- Tant que `knowledge_corpus/sources/` ne contient pas les fiches institutionnelles téléchargées au statut `collected`, le RAG renvoie `insufficient_sources`.
- `confidence` et `evidence.page` ne sont pas encore calculés (valeurs `null`).