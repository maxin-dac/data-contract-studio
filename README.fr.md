
# Data Contract Studio

Data Contract Studio est une application Streamlit qui profile des datasets CSV,
génère des contrats de données structurés au format YAML/JSON, puis valide les
datasets contre ces contrats.

## Fonctionnalités

- Téléversement CSV avec détection d’encodage et de délimiteur
- Profiling automatique des colonnes
- Génération de contrat de données YAML
- Édition manuelle du contrat
- Rapport de validation avec règles pass/fail
- Export du contrat et du rapport en YAML, JSON, Markdown, HTML

## Lancer localement

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py