import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import glob
import pandas as pd
from scripts.utils.read_config import cfg

#===========config===========
csvs_dir = cfg['spectrum']['path']['spectrums']

list_datafilename = sorted(glob.glob(os.path.join(csvs_dir, "*.csv")))

result_figure = os.path.join(csvs_dir, "figure.png")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [2, 1]}, constrained_layout=True)
plt.subplots_adjust(hspace=0.0)

colors = ["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
i=0

for file in list_datafilename:
  print(f"{file=}")
  name = file.split("_")[0].split("/")[1]

  df = pd.read_csv(file)
  x_vals = df['Energy_keV']
  x_err = df['Energy_Error_keV']
  y_net = df['Net_Counts']
  y_err = df['Net_Error']
  y_mod = df['Model_Values']
  res_sig = df['Residuals_Sigma']

  ax1.errorbar(x_vals, y_net, xerr=x_err, yerr=y_err, fmt='.', label=f'Net({name})', alpha=0.3, color=colors[i])

  ax1.plot(x_vals, y_mod, label=f'{name}(model)', linewidth=2, color=colors[i])

  trigger_sigma = 2

  filter_list = (df['Residuals_Sigma']<-trigger_sigma)|(trigger_sigma<df['Residuals_Sigma'])

  res_sig = res_sig[filter_list]
  x_vals = x_vals[filter_list]
  x_err = x_err[filter_list]

  ax2.errorbar(x_vals, res_sig, xerr=x_err, yerr=1, fmt='.', alpha=0.6, label=f"Residuals({name})", color=colors[i])

  i += 1

fig.suptitle(f'GRB221009A NICER Spectrums')

ax1.set_xscale('log')
ax1.set_yscale('log')
ax1.set_ylabel(r'Counts s$^{-1}$ keV$^{-1}$')
ax1.legend(framealpha=0.1, bbox_to_anchor=(1.05, 1), loc='upper left')
ax1.grid(True, which="both", ls="--", alpha=0.3)

ax2.axhline(0,color="black", linestyle='--', alpha=0.5)
ax2.set_xscale('log')
ax2.set_ylabel('(Data-Model)/Error')
ax2.set_xlabel('Energy (keV)')
ax2.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
ax2.legend(framealpha=0.1, bbox_to_anchor=(1.05, 1), loc='upper left')
ax2.grid(True, which="both", ls=":", alpha=0.5)

fig.savefig(result_figure)
print(f"\nグラフを '{result_figure}' に保存しました。")