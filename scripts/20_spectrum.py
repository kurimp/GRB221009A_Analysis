import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import csv

ObsID = "5420250101"

# 比較したいモデルのリスト
# "モデル名": { "expr": "XSPECの式", "params": { パラメータ番号: "初期値設定文字列" } }
MODELS = {
  "PL": {
    "expr": "tbabs * powerlaw",
    "params": {
      1: "0.5 0.1 0.0 0.0 100.0 100.0",   # nH
      2: "1.5 0.1 -2.0 -2.0 5.0 5.0",     # Gamma
      3: "2.0 0.01 0.0 0.0 1e10 1e10"     # Norm
    }
  },
  "CutoffPL": {
    "expr": "tbabs * cutoffpl",
    "params": {
      1: "0.5 0.1 0.0 0.0 100.0 100.0",   # nH
      2: "1.5 0.1 -2.0 -2.0 5.0 5.0",     # Gamma
      3: "1.0 1.0 0.1 0.1 500.0 500.0",  # HighECut (keV)
      4: "2.0 0.01 0.0 0.0 1e10 1e10"     # Norm
    }
  }
}

def load_data(ObsID, bkgtype="3c50"):
  xspec.AllData.clear()
  xspec.AllModels.clear()

  xspec.Fit.statMethod = "chi"
  obs_directory = os.path.join("/home/heasoft/data", ObsID)
  arf_filename = f"ni{ObsID}.arf"
  rmf_filename = f"ni{ObsID}.rmf"
  if bkgtype == "3c50":
    data_filename = f"ni{ObsID}_tot.pi"
    bkg_filename = f"ni{ObsID}_bkg_3c50.pi"
  elif bkgtype == "scorpion":
    data_filename = f"ni{ObsID}_src.pha"
    bkg_filename = f"ni{ObsID}_bkg_scorp.pha"
  else:
    print("bkgtype must be either '3c50' or 'scorpion'.")

  data_file = os.path.join(obs_directory, data_filename)
  arf_file = os.path.join(obs_directory, arf_filename)
  rmf_file = os.path.join(obs_directory, rmf_filename)
  bkg_file = os.path.join(obs_directory, bkg_filename)
  
  try:
    s = xspec.Spectrum(data_file)
    
    xspec.AllModels.systematic = 0.01
    
    s.background = bkg_file
    
    s.response = rmf_file
    s.response.arf = arf_file
    
    print(f"Loaded: {s.fileName}")
    
    s.ignore("**-0.3 10.0-**")
    
    return s
    
  except Exception as e:
    print(f"データ読み込みエラー: {e}")
    return None

def run_fit(model_config):
  xspec.AllModels.clear()
  print(f"\n--- Defining Model: {model_config['expr']} ---")
  
  m = xspec.Model(model_config['expr'])
  
  for idx, val_str in model_config['params'].items():
    m(idx).values = val_str
  
  xspec.Fit.renorm()
  xspec.Fit.nIterations = 100
  xspec.Fit.query = "yes"
  xspec.Fit.perform()
  
  chi2 = xspec.Fit.statistic
  dof = xspec.Fit.dof
  red_chi2 = chi2 / dof if dof > 0 else 0
  
  xspec.Plot.xAxis = "keV"
  xspec.Plot("data")
  m_vals = xspec.Plot.model()
  
  return m, chi2, red_chi2, m_vals

def treat_data(s):
  xspec.Plot.xAxis = "keV"
  xspec.Plot("data")
  x_vals = xspec.Plot.x()
  x_err = xspec.Plot.xErr()
  y_net = xspec.Plot.y()
  y_err = xspec.Plot.yErr()
  
  xspec.Plot.xAxis = "keV"
  xspec.Plot('Background')
  y_bkg  = xspec.Plot.y()
  
  y_tot = [n + b for n, b in zip(y_net, y_bkg)]
  
  return x_vals, x_err, y_net, y_err, y_bkg, y_tot

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
plt.subplots_adjust(hspace=0.0)

for bkgtype in ["3c50", "scorpion"]:
  if bkgtype=="scorpion":
    pass
  x_vals, x_err, y_net, y_err, y_bkg, y_tot = treat_data(load_data(ObsID, bkgtype))
  
  ax1.errorbar(x_vals, y_tot, fmt='.', label=f'Total({bkgtype})', alpha=0.3)
  ax1.errorbar(x_vals, y_net, yerr=y_err, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
  ax1.step(x_vals, y_bkg, where='mid', label=f'Background({bkgtype})', alpha=0.3)
  
  for i, (name, config) in enumerate(MODELS.items()):
    pass
    m, chi2, red_chi2, m_vals = run_fit(config)
    
    print(f"[{name}] Red.Chi2: {red_chi2:.2f}")
    
    if max(m_vals) > 0:
      ax1.plot(x_vals, m_vals, label=f'{name}({bkgtype})($\chi^2_\\nu$={red_chi2:.2f})', linewidth=2)
    
    residuals = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y_net, m_vals, y_err)]
    ax2.errorbar(x_vals, residuals, fmt='.', alpha=0.6, label=f"Residuals({bkgtype})({name})")
    
    row_data = list(zip(*[x_vals, y_tot, y_net, m_vals, y_err]))
    with open(f'results/result({bkgtype})({name}).csv', 'w', newline='') as f:
      writer = csv.writer(f)
      writer.writerow(['x_vals', 'y_tot', 'y_net', 'm_vals', 'y_err'])
      writer.writerows(row_data)

fig.suptitle(f'GRB221009A NICER Spectrum Fit')

ax1.set_xscale('log')
ax1.set_yscale('log')
ax1.set_ylabel('Counts s$^{-1}$ keV$^{-1}$')
ax1.legend(framealpha=0.1)
ax1.grid(True, which="both", ls="--", alpha=0.3)

ax2.axhline(0,color="black", linestyle='--', alpha=0.5)
ax2.set_xscale('log')
ax2.set_ylabel('(Data-Model)/Error')
ax2.set_xlabel('Energy (keV)')
#ax2.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
ax2.legend(framealpha=0.1)
ax2.grid(True, which="both", ls=":", alpha=0.5)

fig.savefig("results/spectrum_fit.png")
print("\nグラフを 'results/spectrum_fit.png' に保存しました。")