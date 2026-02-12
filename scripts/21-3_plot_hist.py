import matplotlib.pyplot as plt
import numpy as np
from scripts.utils.read_config import cfg as default_cfg
import os
import sys
import glob
import re
import pandas as pd

plt.rcParams.update({
  "axes.labelsize": 20,      # 軸ラベルのサイズ
  "xtick.labelsize": 24,     # x軸目盛りのサイズ
  "ytick.labelsize": 24,     # y軸目盛りのサイズ
  "lines.linewidth": 3,      # プロット線の太さ
  "lines.markersize": 10,    # マーカーの大きさ
  "legend.fontsize": 16,     # 凡例のサイズ
  "axes.linewidth": 2,       # グラフ枠線の太さ
  "xtick.major.width": 2,    # 目盛り線の太さ
  "ytick.major.width": 2,
  "savefig.dpi": 300         # 保存時の解像度（高めに設定）
})

norm_target = [0.009]
weight = 1
trigger = 9.07
observed = 2.52

def run_plot(cfg):
  file_name = cfg['spectrum']['path']['merge_name']
  OUTPUT_DIR = f"results/spectrum/{file_name}"

  list_candidate_file_mc  = sorted(glob.glob(os.path.join(OUTPUT_DIR, "mc_results", "seglist_*_mc_*.csv")))
  list_candidate_file_limit  = sorted(glob.glob(os.path.join(OUTPUT_DIR, "limit_results", "seglist_*_limit_*.csv")))

  try:
    latest_file_mc = max(
      list_candidate_file_mc,
      key=lambda f: int(re.search(r'limit_([0-9]+)', os.path.basename(f)).group(1)) if re.search(r'limit_([0-9]+)', os.path.basename(f)) else 0
    )
    latest_file_limit = max(
      list_candidate_file_limit,
      key=lambda f: int(re.search(r'limit_([0-9]+)', os.path.basename(f)).group(1)) if re.search(r'limit_([0-9]+)', os.path.basename(f)) else 0
    )

    print(f"Using MC Result: {os.path.basename(latest_file_mc)}")
    print(f"Using limit Result: {os.path.basename(latest_file_limit)}")
    mc_data = pd.read_csv(latest_file_mc)
    limit_data = pd.read_csv(latest_file_limit)

  except Exception as e:
    print(f"データ読み込みエラー: {e}")
    sys.exit(1)

  fig_hist, ax1_hist = plt.subplots(1, 1, figsize=(10, 6), constrained_layout=True)

  max_d_chi2 = np.max(limit_data['Delta_Chi2'])
  bins_d_chi2 = np.arange(0, max_d_chi2 + 1.0, 1)

  ax1_hist.hist(mc_data['Simulated_Delta_Chi2'], bins=bins_d_chi2, edgecolor='black', alpha=0.7, label='Simulated Base')

  norm_unique = limit_data['Norm'].unique()

  processed_any = False
  norm_target_str = [f"{norm:.8e}" for norm in norm_target]
  for norm in norm_unique:
    norm_str = f"{norm:.8e}"
    if norm_str not in norm_target_str:
      continue
    processed_any = True
    data = limit_data[limit_data['Norm']==norm]['Delta_Chi2']
    print(f"Plotting Norm: {norm_str}, Data points: {len(data)}")
    ax1_hist.hist(data, weights=np.ones_like(data), bins=bins_d_chi2*weight, edgecolor='black', alpha=0.3, label=f'Injected($\mathrm{{Norm}}={float(norm):.1e}$))')

  if not processed_any:
    raise ValueError(f"Error: None of the target norms {norm_target_str} were found in the dataset. Available norms are: {norm_unique}")

  ax1_hist.axvline(trigger, linestyle='-', alpha=0.2, label=f"threshold($\Delta\chi^2={trigger:.2f}$)")
  ax1_hist.axvline(observed, linestyle='--', alpha=0.2, label=f"observed($\Delta\chi^2={observed:.2f}$)")

  ax1_hist.set_xlabel(r'$\Delta \chi^2$ (Base - Comp)')
  ax1_hist.set_ylabel('Frequency')
  ax1_hist.set_yscale('log')
  ax1_hist.legend()
  ax1_hist.set_xlim(0, 100)
  ax1_hist.grid(True, alpha=0.3)

  plot_path = os.path.join(OUTPUT_DIR, f"{file_name}_hists.png")
  fig_hist.savefig(plot_path)

  print(f"Saved MC Plot: {plot_path}")

if __name__ == "__main__":
  run_plot(default_cfg)