# 1. Genera dataset

uv run python -m scripts.simulate_game --games 100000 --output scr/scripts/artifacts/marafone_dataset.csv

# 2. Allena il modello

uv run python -m scripts.train_model --data scr/scripts/artifacts/marafone_dataset.csv
