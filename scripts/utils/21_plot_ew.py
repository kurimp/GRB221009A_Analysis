import matplotlib.pyplot as plt
import os
import pandas as pd

plt.rcParams.update({
  "axes.labelsize": 15,      # 軸ラベルのサイズ
  "xtick.labelsize": 24,     # x軸目盛りのサイズ
  "ytick.labelsize": 18,     # y軸目盛りのサイズ
  "lines.linewidth": 3,      # プロット線の太さ
  "lines.markersize": 10,    # マーカーの大きさ
  "axes.linewidth": 2,       # グラフ枠線の太さ
  "xtick.major.width": 2,    # 目盛り線の太さ
  "ytick.major.width": 2,
  "savefig.dpi": 300         # 保存時の解像度（高めに設定）
})

lc_path = os.path.join("results", "lightcurve", "seg02", "bin120", "from30to1000", "data.csv")
ew_path = os.path.join("results", "spectrum", "sim_eq.csv")

df_lc = pd.read_csv(lc_path)
df_ew = pd.read_csv(ew_path)

# プロット
fig, (ax1, ax3, ax2) = plt.subplots(3, 1, figsize=(10, 9), sharex=True, gridspec_kw={'height_ratios': [2, 3, 3]}, constrained_layout=True)

ax1.errorbar(df_lc['time'], df_lc['rate'], yerr=df_lc['error'], fmt='x', capsize=0)
sca_ax2 = ax2.scatter(df_ew['middle'], df_ew['eq_val'], marker='x', c=df_ew['width']*2)
sca_ax3 = ax3.scatter(df_ew['middle'], df_ew['norm'], marker='x', c=df_ew['width']*2)

ax1.set_ylabel("Rate (counts/s)")
ax1.set_xscale('log')
ax1.set_xlim(1e4, 1e6)
ax1.set_yscale('log')
ax1.grid(True, which='both', axis='both', linestyle='--', alpha=0.3)

ax2.axhline(0, color="black", linestyle='--', alpha=0.5)
ax2.set_xlabel("Elapsed Time from the Fermi-GBM trigger\n(2022 October 9 at 13:16:59.99 UTC) (seconds)")
ax2.set_ylabel(r"Equivalent Width($\text{keV}$)")
ax2.set_yscale('log')
ax3.set_ylim(1e-2, 3e0)
ax2.grid(True, which='both', axis='both', linestyle='--', alpha=0.3)

ax3.axhline(0, color="black", linestyle='--', alpha=0.5)
ax3.set_ylabel(r"Norm($\text{photons cm}^{-2} \text{s}^{-1}$)")
ax3.set_yscale('log')
ax3.set_ylim(2e-5, 1e-2)
ax3.grid(True, which='both', axis='both', linestyle='--', alpha=0.3)

fig.colorbar(sca_ax2, ax=[ax3, ax2], label=r"Exposure ($s$)", location='right', aspect=40)

fig.savefig("EW.png")
