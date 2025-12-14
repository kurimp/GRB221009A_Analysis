import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os

#===========config===========
#使用するデータのパス
data_file_path = "results/lightcurve/bin60/from1200to1500/data.csv"

#表示するヒストグラムのbinの幅、及び表示範囲
width = 0.01
min = 0
max = 0.5

df = pd.read_csv(data_file_path)

fig, ax = plt.subplots(figsize=(10, 6))

if not (max-min) % width == 0:
  max += (width - (max-min) % width)

bin_count = int((max-min) // width + 1)

bins = np.arange(min, max + width, width)

freq = df['rate'].value_counts(bins=bins, sort=False)

class_value = (bins[:-1] + bins[1:])/2
rel_freq = freq / df['rate'].count()
cum_freq = freq.cumsum()
rel_cum_freq = rel_freq.cumsum()

dist = pd.DataFrame(
  {
    "class_value": class_value,
    "frequancy": freq,
    "rel_freq": rel_freq,
    "cum_freq": cum_freq,
    "rel_cum_freq": rel_cum_freq,
  },
  index=freq.index
)

print(dist)

ax.bar(dist['class_value'], dist['frequancy'], width=width)
ax.axvline(0.048, linestyle='--', color="black", alpha=0.5)

ax.set_xscale('linear')
#ax.set_yscale('log')
ax.set_xlim(min-min*0.05, max+max*0.05)

ax.set_title(f"Count Rate Histogram of GRB 221009A Light Curve")
ax.set_xlabel('Count Rate (counts/s)')
ax.set_ylabel('Frequency')

ax.minorticks_on()
plt.tight_layout()

#各種データの保存
result_folder_path = os.path.dirname(data_file_path)

FrequencyDistribution_path = os.path.join(result_folder_path, f"FrequencyDistribution.csv")
result_data_path = os.path.join(result_folder_path, f"data.csv")
CountRateHist_path = os.path.join(result_folder_path, f"CountRateHist.png")

dist.to_csv(FrequencyDistribution_path)
plt.savefig(CountRateHist_path, format="png", dpi=300)