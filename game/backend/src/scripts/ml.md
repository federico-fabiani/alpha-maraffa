# 1. Genera dataset

uv run python -m scripts.simulate_game --games 100000 --output src/scripts/artifacts/marafone_dataset.csv

# 2. Allena il modello

uv run python -m scripts.train_model --data src/scripts/artifacts/marafone_dataset.csv

# 3. Analisi strategie (report Markdown)

uv run python -m scripts.analyze_model \
    --data  src/scripts/artifacts/marafone_dataset.csv \
    --model src/scripts/artifacts/marafone_model.joblib \
    --out   src/scripts/artifacts/strategy_report.md

# Opzioni extra:
#   --top-features 40     numero feature nell'importance chart
#   --shap                aggiungi analisi SHAP (uv add shap prima)
