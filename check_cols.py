import pandas as pd
df = pd.read_excel('data/prevision_2026.xlsx', sheet_name='PREVISION 01.26-(PI%)', header=1)
with open('cols.txt', 'w', encoding='utf-8') as f:
    for col in df.columns:
        f.write(str(col) + '\n')
