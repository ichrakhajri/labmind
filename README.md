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
    pytest

## Structure
    backend/app/core/            configuration
    backend/app/extraction/      PDF (texte natif) et OCR Tesseract
    backend/app/identification/  catalogue d'alias, parsing des lignes
    backend/app/validation/      contrôles techniques, comparaison arithmétique à la fourchette du laboratoire
    backend/app/schemas.py       schémas Pydantic (base du contrat API)
    backend/tests/               tests automatisés
    docs/api-contract/           contrat API v1 + exemples JSON
    docs/decisions/              décisions techniques

## État du projet (fin de l'Étape 1)
Fait :
- Prototype Colab modularisé, exécutable localement, couvert par des tests.
- Contrat API v1 rédigé et transmis au frontend (aucun endpoint implémenté).

Pas encore fait :
- Retrait des conseils et questions figés du prototype (Étape 2).
- RAG et corpus documentaire (Étape 3).
- Agent à outils avec confirmation utilisateur (Étape 4).
- Catalogue complet (6 catégories), benchmark OCR, jeu d'évaluation indépendant (Étape 5).
- API, tâches asynchrones, base de données, PDF, suppression des données (Étapes 6 à 8).

## Dette connue
- Le contenu médical figé (conseils, questions, descriptions) vit encore dans le notebook, pas dans ce dépôt : il n'a volontairement pas été migré.
- Les tests utilisent des documents générés par nos soins : ils détectent des régressions mais ne prouvent pas la performance sur de vrais comptes rendus.
- `confidence` et `evidence.page` ne sont pas calculés (valeurs `null`).