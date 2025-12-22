import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
from scipy.optimize import curve_fit
from scripts.utils.read_config import cfg

#===========config===========
#使用するデータのパス
data_file_path = cfg['lightcurve']['path']['data-for-hist']

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
    "frequency": freq,
    "rel_freq": rel_freq,
    "cum_freq": cum_freq,
    "rel_cum_freq": rel_cum_freq,
  },
  index=freq.index
)

print(dist)

#解析結果の表示
ax.bar(dist['class_value'], dist['frequency'], width=width)

#正規分布でのフィッティング
def gaussian_func(x, A, mu, sigma):
  return A * np.exp( - (x - mu)**2 / (2 * sigma**2))

parameter_initial = np.array([400, 0.048, 0.018])
sigma_errors = np.sqrt(dist['frequency'])
popt, pcov = curve_fit(gaussian_func, dist['class_value'], dist['frequency'], p0=parameter_initial, sigma=sigma_errors, absolute_sigma=True, maxfev=100000)
fit_norm_x = np.arange(min, max, width * 0.1)
fit_norm_y = gaussian_func(fit_norm_x, popt[0], popt[1], popt[2])

re_parameter_initial = np.array([popt[0],popt[1], popt[2]])

print(re_parameter_initial)

re_dist = dist[(popt[1]-popt[2]*3 < dist['class_value'])&(dist['class_value'] < popt[1]+popt[2]*3)]

print(re_dist)

re_sigma_errors = np.sqrt(re_dist['frequency'])
re_popt, re_pcov = curve_fit(gaussian_func, re_dist['class_value'], re_dist['frequency'], p0=re_parameter_initial, sigma=re_sigma_errors, absolute_sigma=True, maxfev=100000)
re_fit_norm_x = np.arange(popt[1]-popt[2]*2, popt[1]+popt[2]*2, width * 0.1)
re_fit_norm_y = gaussian_func(re_fit_norm_x, re_popt[0], re_popt[1], re_popt[2])

ax.plot(re_fit_norm_x, re_fit_norm_y, label=f"Fitted normal distribution:$A={re_popt[0]:2f}$, $\mu={re_popt[1]:2f}$, $\sigma={re_popt[2]:2f}$", color="green")

#正規分布の表示
rep_norm_x = np.arange(0.048-0.018*2, 0.048+0.018*2, width * 0.1)
rep_norm_y = gaussian_func(rep_norm_x, re_popt[0], 0.048, 0.018)
ax.plot(rep_norm_x, rep_norm_y, label=f"Reported normal distribution:$A={re_popt[0]:2f}$, $\mu=0.048$, $\sigma=0.018$", color="red")
ax.axvline(0.048, linestyle='--', color="black", alpha=0.5)
ax.set_xscale('linear')
#ax.set_yscale('log')
ax.set_xlim(min-min*0.05, max+max*0.05)

ax.set_title("Count Rate Histogram of GRB 221009A Light Curve")
ax.set_xlabel('Count Rate (counts/s)')
ax.set_ylabel('Frequency')

ax.minorticks_on()
ax.legend()
plt.tight_layout()

#各種データの保存
result_folder_path = os.path.dirname(data_file_path)

FrequencyDistribution_path = os.path.join(result_folder_path, "FrequencyDistribution.csv")
result_data_path = os.path.join(result_folder_path, "data.csv")
CountRateHist_path = os.path.join(result_folder_path, "CountRateHist.png")

dist.to_csv(FrequencyDistribution_path)
plt.savefig(CountRateHist_path, format="png", dpi=300)