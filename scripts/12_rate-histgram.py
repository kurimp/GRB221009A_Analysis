import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
from scipy.stats import norm
from scipy.optimize import curve_fit

#===========config===========
#使用するデータのパス
data_file_path = "results/lightcurve/seg/bin120/from1200to1500/data.csv"

#表示するヒストグラムのbinの幅、及び表示範囲
width = 0.01
min = 0
max = 0.5

#======================

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

#正規分布でのフィッティング
def gaussian_func(x, A, mu, sigma):
  return A * np.exp( - (x - mu)**2 / (2 * sigma**2))

parameter_initial = np.array([400, 0.048, 0.018])

popt, pcov = curve_fit(gaussian_func, dist['class_value'], dist['frequancy'], p0=parameter_initial, maxfev=100000)
fit_norm_x = np.arange(min, max, width * 0.1)
fit_norm_y = gaussian_func(fit_norm_x, popt[0], popt[1], popt[2])

re_parameter_initial = np.array([popt[0],popt[1], popt[2]])

print(re_parameter_initial)

re_dist = dist[(popt[1]-popt[2]*3 < dist['class_value'])&(dist['class_value'] < popt[1]+popt[2]*3)]

print(re_dist)

re_popt, re_pcov = curve_fit(gaussian_func, re_dist['class_value'], re_dist['frequancy'], p0=re_parameter_initial, maxfev=100000)
re_fit_norm_x = np.arange(popt[1]-popt[2]*3, popt[1]+popt[2]*3, width * 0.1)
re_fit_norm_y = gaussian_func(re_fit_norm_x, re_popt[0], re_popt[1], re_popt[2])

ax.plot(re_fit_norm_x, re_fit_norm_y, label=f"Fitted normal distribution:$A={popt[0]:2f}$, $\mu={popt[1]:2f}$, $\sigma={popt[2]:2f}$", color="green")

#正規分布の表示
rep_norm_x = np.arange(0.048-0.018*3, 0.048+0.018*3, width * 0.1)
rep_norm_y = norm.pdf(rep_norm_x, loc=0.048, scale=0.018)*0.7
ax.plot(rep_norm_x, rep_norm_y, label="Reported normal distribution", color="red")
ax.set_xscale('linear')
#ax.set_yscale('log')
ax.set_xlim(min-min*0.05, max+max*0.05)

ax.set_title(f"Count Rate Histogram of GRB 221009A Light Curve")
ax.set_xlabel('Count Rate (counts/s)')
ax.set_ylabel('Frequency')

ax.minorticks_on()
ax.legend()
plt.tight_layout()

#各種データの保存
result_folder_path = os.path.dirname(data_file_path)

FrequencyDistribution_path = os.path.join(result_folder_path, f"FrequencyDistribution.csv")
result_data_path = os.path.join(result_folder_path, f"data.csv")
CountRateHist_path = os.path.join(result_folder_path, f"CountRateHist.png")

dist.to_csv(FrequencyDistribution_path)
plt.savefig(CountRateHist_path, format="png", dpi=300)