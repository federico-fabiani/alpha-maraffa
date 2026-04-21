import pandas as pd
from pathlib import Path

bris_cols = [f'hand_briscola_{r}' for r in range(1, 11)]
results = {}

for v in range(1, 9):
    path = Path(f'game/backend/artifacts/training/v{v}/marafone_analysis_dataset.parquet')
    if not path.exists():
        print(f'v{v}: file non trovato')
        continue
    df = pd.read_parquet(path)
    selector_map = (
        df[(df['round_num']==1) & (df['turn_num']==1) & (df['play_order']==0)]
        [['game_id','seat']].rename(columns={'seat':'selector_seat'})
    )
    df2 = df.merge(selector_map, on='game_id')
    sel_lead = df2[(df2['seat'] == df2['selector_seat']) & (df2['play_order'] == 0)].copy()
    sel_lead['n_bris_hand'] = sel_lead[bris_cols].sum(axis=1)
    grp = sel_lead.groupby('n_bris_hand').agg(
        totale=('card_is_briscola','count'),
        gioca_briscola=('card_is_briscola','sum')
    ).reset_index()
    grp['pct'] = grp['gioca_briscola'] / grp['totale'] * 100
    results[f'v{v}'] = grp.set_index('n_bris_hand')['pct']

# Tabella pivot: righe = n_bris_hand, colonne = versioni
pivot = pd.DataFrame(results).round(1)
pivot.index.name = 'briscole_in_mano'
print(pivot.to_string())