import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

df = pd.read_csv("data/60s-01/data_lc_1200-1500.csv")

fig, ax = plt.subplots(figsize=(10, 6))

width = 0.01
min = 0
max = 700

if not (max-min) % width == 0:
  max += (width - (max-min) % width)

bin_count = int((max-min) // width + 1)

bins = np.linspace(min, max, bin_count)

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

dist.to_csv("FrequencyDistribution.csv")

print(dist)

ax.bar(dist['class_value'], dist['frequancy'], width=width)
ax.axvline(0.36666667, linestyle='--', color="black", alpha=0.5)

ax.set_xscale('linear')
ax.set_yscale('log')
ax.set_xlim(0, 15)

ax.set_title(f"Count Rate Histogram of GRB 221009A Light Curve (ch. 1200-1500)")
ax.set_xlabel('Count Rate (counts/s)')
ax.set_ylabel('Frequency (count)')

ax.minorticks_on()
plt.tight_layout()

plt.savefig(f"CountRateHist.png", format="png", dpi=300)