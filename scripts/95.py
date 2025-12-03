import pandas as pd

#df = pd.read_csv("dat/data_lc_1200-1500_by_ObsID.csv").dropna().sort_values('rate')
df = pd.read_csv("data/nicerl3_60s/data_lc_1200-1500.csv").dropna().sort_values('rate')

print(df['rate'].quantile(0.95))