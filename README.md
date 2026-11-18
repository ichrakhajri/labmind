# LabMind

Application web **informative** : analyse pédagogique d'un compte rendu d'analyses biologiques (PDF ou image).
LabMind ne pose aucun diagnostic et ne prescrit aucun traitement.

## Prérequis
- Python 3.10+
- Tesseract OCR avec le pack français (`tesseract --list-langs` doit afficher `fra`)
- Git

## Installation (Windows, PowerShell)
    cd backend
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt

## Configuration
Variables d'environnement optionnelles (voir `backend/.env.example`) :
`LABMIND_TESSERACT_CMD`, `LABMIND_OCR_LANG`, `LABMIND_DATA_DIR`, `LABMIND_MAX_UPLOAD_BYTES`.

## Tests
    cd backend
    pytest -v

## Structure
    backend/app/core/            configuration
    backend/app/extraction/      PDF (texte natif) et OCR Tesseract
    backend/app/identification/  catalogue d'alias, parsing des lignes
    backend/app/validation/      contrôles techniques, comparaison arithmétique à la fourchette du laboratoire
    backend/app/generation/      contrat d'explications sourcées et repli neutre (sans règles médicales)
    backend/app/schemas.py       schémas Pydantic (base du contrat API v1)
    backend/tests/               tests automatisés (dont garde-fou anti-système-expert)
    docs/api-contract/           contrat API v1 + exemples JSON
    docs/archive/                prototype Colab archivé (lecture seule, non conforme)
    docs/decisions/              décisions techniques

## État du projet (fin de l'Étape 2)
Fait :
- Prototype Colab modularisé, exécutable localement, couvert par des tests.
- Contrat API v1 rédigé et validé avec le frontend (aucun endpoint implémenté).
- Retrait complet du système expert et verrouillage automatisé par analyse AST (`test_no_expert_system.py`).
- Interface de génération sourcée (`app/generation/`) et comportement neutre « source insuffisante ».
- Notebook prototype archivé en lecture seule dans `docs/archive/`.

Pas encore fait :
- Corpus documentaire institutionnel, indexation et RAG + LLM local (Étape 3).
- Agent à outils avec confirmation utilisateur `waiting_for_user` (Étape 4).
- Catalogue complet (6 catégories), benchmark OCR, jeu d'évaluation indépendant (Étape 5).
- API FastAPI, tâches asynchrones, base de données, rapport PDF, suppression des données (Étapes 6 à 8).

## Dette connue
- Aucune explication médicale n'est encore générée tant que le corpus et le RAG (Étape 3) ne sont pas construits : le générateur de repli retourne `insufficient_sources`.
- Les tests d'extraction utilisent des documents synthétiques : ils détectent des régressions mais ne prouvent pas la performance sur de vrais comptes rendus (Étape 5).
- `confidence` et `evidence.page` ne sont pas calculés (valeurs `null`).