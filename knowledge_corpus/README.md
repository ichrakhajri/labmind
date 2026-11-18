# Corpus documentaire LabMind

Ce dossier rassemble les documents de référence utilisés par le futur module RAG.

## Arborescence
- `sources/` : textes bruts nettoyés (`.txt` ou `.md`) issus de sources officielles vérifiées.
- `processed/` : passages découpés et métadonnées prêtes pour l'indexation (Étape 3.2).
- `metadata/sources_registry.json` : registre officiel des sources (traçabilité et statut).

## Règles de sélection des sources
1. **Organismes autorisés** : institutions publiques de santé, agences sanitaires et sociétés savantes (HAS, Inserm, Assurance Maladie / ameli.fr, ANSES, Santé publique France / MangerBouger, sociétés savantes médicales).
2. **Traçabilité obligatoire** avant passage au statut `collected` :
   - `source_id` unique et stable (ex. `ameli-nfs-2025`) ;
   - `url` exacte de la page ou du PDF source (jamais une simple page d'accueil) ;
   - `published_date` (date de publication ou de mise à jour lue sur le document) ;
   - `reuse_conditions` (mentions légales / licence vérifiées) ;
   - `local_filename` présent et non vide dans `sources/`.
3. **Zéro contenu inventé** : aucun résumé rédigé de mémoire ne doit être placé dans `sources/`.

## Catégories cibles
- `nfs` (hémogramme : HGB, WBC, RBC, PLT, HCT)
- `bilan_martial` (fer, ferritine, transferrine)
- `bilan_glycemique` (glycémie, HbA1c)
- `bilan_lipidique` (cholestérol total, HDL, LDL, triglycérides)
- `bilan_hepatique` (ALAT, ASAT, GGT, bilirubine)
- `bilan_renal` (créatinine, urée, DFG estimé)
- `hygiene_de_vie` (repères généraux alimentation / activité physique)