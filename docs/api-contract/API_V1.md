# LabMind : contrat API v1 (brouillon à valider avec le frontend)

Base : `/v1`. Format : JSON (UTF-8), sauf upload (multipart) et téléchargement PDF.
Aucune authentification ni compte. L'accès à une tâche repose sur son `task_id` (UUID4).

## 1. Cycle de vie d'une tâche

received -> processing -> done
                |   ^
                v   |
         waiting_for_user      (l'agent attend une réponse, puis reprend)
                |
                +-> error       (échec non récupérable)

| État | Signification | Action du frontend |
|---|---|---|
| received | Fichier reçu, pas encore traité | Continuer le polling |
| processing | Traitement en cours | Continuer le polling (toutes les 2 s) |
| waiting_for_user | L'agent a besoin d'une réponse | Afficher `pending_question`, puis POST de la réponse |
| done | Résultat prêt | Afficher le résultat, proposer le PDF |
| error | Échec | Afficher `errors[0].message` |

## 2. Endpoints

| Méthode | Route | Rôle |
|---|---|---|
| GET | /v1/health | Vérifier que le service répond |
| POST | /v1/tasks | Déposer un document (multipart, champ `file`) -> 202 |
| GET | /v1/tasks/{task_id} | Statut et résultat courant |
| POST | /v1/tasks/{task_id}/answer | Répondre à la question en attente |
| GET | /v1/tasks/{task_id}/report.pdf | Télécharger le rapport PDF (état `done`) |
| DELETE | /v1/tasks/{task_id} | Supprimer fichier, résultats et artefacts -> 204 |

## 3. Codes HTTP

| Code | Cas | `error.code` |
|---|---|---|
| 202 | Document accepté | |
| 200 | Lecture réussie | |
| 204 | Suppression réussie | |
| 400 | Requête mal formée (champ manquant) | invalid_request |
| 404 | task_id inconnu ou déjà supprimé | task_not_found |
| 409 | Action impossible dans l'état courant (ex. réponse sans question en attente, PDF avant `done`) | invalid_state |
| 413 | Fichier trop gros (défaut 10 Mo) | file_too_large |
| 415 | Format non supporté (pdf, png, jpg, jpeg) | unsupported_format |
| 422 | Fichier illisible, ou réponse invalide à la question | unreadable_document / invalid_answer |
| 500 | Erreur interne | internal_error |

Corps d'erreur HTTP :
```json
{"error": {"code": "unsupported_format", "message": "Format non supporté (pdf, png, jpg, jpeg)."}}
```
Aucun contenu médical (valeurs, noms de paramètres) ne doit apparaître dans un message d'erreur ni dans les journaux.

## 4. Objet Task (réponse de GET /v1/tasks/{id})

| Champ | Type | Remarque |
|---|---|---|
| task_id | string | UUID4 |
| status | enum | cf. §1 |
| document | objet ou null | `filename`, `extraction_method` (`pdf_text` ou `ocr`) |
| detected_categories | string[] | À venir (Étape 5) ; vide pour l'instant |
| parameters | ParameterResult[] | cf. §5 |
| pending_question | objet ou null | cf. §6, non nul seulement en `waiting_for_user` |
| report_id | string ou null | non nul seulement en `done` |
| explanations | objet ou null | À venir (Étape 3 : texte + citations) |
| sources | Source[] | À venir (Étape 3) |
| disclaimer | string | Message de précaution unique, toujours présent |
| errors | ErrorInfo[] | Non vide seulement en `error` |

Le frontend doit ignorer les champs inconnus (le contrat évolue en ajoutant des champs, jamais en changeant leur sens dans /v1).

## 5. ParameterResult

| Champ | Type | Remarque |
|---|---|---|
| code | string | Identifiant technique (HGB, GLY...) |
| name_printed | string | Nom tel qu'imprimé dans le document |
| value | number ou null | |
| unit | string ou null | |
| reference | {min, max, origin} | `origin` = `document_laboratoire` si présente, sinon null. Jamais inventée |
| status | enum | below_reference, within_reference, above_reference, reference_unavailable, value_unavailable, not_analyzed |
| reason | string ou null | Motif si `not_analyzed` |
| confidence | number ou null | null tant que non calculée |
| evidence | {raw_text, page} | `page` null pour l'instant |

Le statut est une position arithmétique par rapport à la fourchette du laboratoire : pas un jugement médical. L'interface ne doit pas afficher de mot du type « normal / anormal / malade ».

## 6. Confirmation utilisateur (waiting_for_user)

pending_question :
```json
{"question_id": "q-001", "field": "unit", "code": "HCT",
 "message": "L'unité de ce paramètre est illisible. Quelle unité figure sur votre document ?",
 "options": ["%", "autre", "je ne sais pas"]}
```
`field` : `unit`, `value`, `reference_min` ou `reference_max`.

Réponse : POST /v1/tasks/{id}/answer
```json
{"question_id": "q-001", "answer": "%"}
```
- `answer` est toujours une chaîne ; pour une valeur numérique le backend la convertit et la valide.
- « je ne sais pas » est toujours accepté : le paramètre passe en `not_analyzed` (jamais deviné).
- Un `question_id` périmé ou inconnu -> 409 ; une réponse invalide -> 422 (la question reste en attente).
- Une seule question à la fois.

## 7. Source (à venir, Étape 3)
```json
{"source_id": "has-2023-xxx#p4", "title": "...", "organisme": "...", "url": "...", "date": "2023-01-01"}
```
Chaque phrase explicative citera des `source_id`. Toute phrase sans source disponible est signalée comme telle, jamais complétée de mémoire.

## 8. Confidentialité (engagements du backend)
- Fichier déposé supprimé dès la fin du traitement ; résultats supprimés sous une durée de conservation fixée (Étape 7).
- DELETE efface immédiatement tout.
- Aucune URL publique permanente.
## 9. Décisions validées (17/11/2026)
- Polling toutes les 2 s ; arrêt sur done, error ou waiting_for_user.
- Une seule question à la fois ; options affichées en boutons ; « je ne sais pas » toujours présent.
- `disclaimer` fourni par l'API et affiché tel quel.
- Conservation : suppression automatique après 1 h (à confirmer à l'Étape 7) + DELETE manuel.
- Erreurs : {"error": {"code", "message"}} ; le frontend se base sur `code`.
- Évolution du contrat : ajout de champs uniquement dans /v1.