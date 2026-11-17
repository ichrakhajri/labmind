"""Catalogue technique : alias de noms et unités rencontrées.

Aucune valeur de référence médicale ici : les fourchettes proviennent
uniquement du document du laboratoire.
"""

ALIASES = {
    "HGB": ["Hémoglobine", "HGB", "Hb"],
    "WBC": ["Globules blancs", "Leucocytes", "WBC"],
    "RBC": ["Globules rouges", "Hématies", "RBC"],
    "PLT": ["Plaquettes", "PLT"],
    "HCT": ["Hématocrite", "HCT"],
    "GLY": ["Glycémie à jeun", "Glycémie", "Glucose"],
    "CHOL": ["Cholestérol total", "Cholestérol"],
    "HDL": ["Cholestérol HDL", "HDL"],
    "LDL": ["Cholestérol LDL", "LDL"],
    "TG": ["Triglycérides", "TG"],
}

KNOWN_UNITS = ["g/dL", "g/L", "mg/dL", "%", "10^3/µL", "10^6/µL"]

# Unités acceptées par paramètre (validation technique du format, pas d'interprétation)
ACCEPTED_UNITS = {
    "HGB": ["g/dL", "g/L"],
    "WBC": ["10^3/µL"],
    "RBC": ["10^6/µL"],
    "PLT": ["10^3/µL"],
    "HCT": ["%"],
    "GLY": ["g/L", "mg/dL"],
    "CHOL": ["g/L", "mg/dL"],
    "HDL": ["g/L", "mg/dL"],
    "LDL": ["g/L", "mg/dL"],
    "TG": ["g/L", "mg/dL"],
}