# LabMind

Application web **informative** : analyse pédagogique d'un compte rendu d'analyses biologiques (PDF ou image).
LabMind ne pose aucun diagnostic et ne prescrit aucun traitement.

## Prérequis
- Python 3.10+
- Tesseract OCR avec le pack français (`tesseract --list-langs` doit afficher `fra`)

## Installation (Windows, PowerShell)
    cd backend
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt

## Tests
    cd backend
    pytest

## État du projet
Étape 1 en cours : modularisation du prototype issu du notebook.
Dette connue (à retirer à l'Étape 2) : conseils figés et questions prédéfinies du prototype.