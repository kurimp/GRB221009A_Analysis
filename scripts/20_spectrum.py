import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import csv
import sys

#===========config===========
#plotのy軸表記選択。FluxならTrue。
tf_eeufspec = False

#使用するObsIDを選択。
ObsID = "5410670110"
#ObsID = "5420250101"

#scorpionでのbackgroundを扱うかどうかを選択。使うならTrue。
tf_scorpion = True

#特定のモデルのみ処理を実施したい場合、モデル名をlistで与える。なければNone。
only_model = ["ZCutoffPL"]

OUTPUT_DIR = f"results/{ObsID}"

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
  },
  "ZPL": {
    "expr": "ztbabs * powerlaw",
    "params": {
      1: "0.5 0.1 0.0 0.0 100.0 100.0",   # nH (ztbabsの1番目)
      2: "0.151 -0.01 0.0 0.0 10.0 10.0",    # Redshift (ztbabsの2番目) ★追加
      3: "1.5 0.1 -2.0 -2.0 5.0 5.0",     # Gamma (powerlawの1番目 -> 全体で3番目)
      4: "2.0 0.01 0.0 0.0 1e10 1e10"     # Norm (powerlawの2番目 -> 全体で4番目)
    }
  },
  "ZCutoffPL": {
    "expr": "ztbabs * cutoffpl",
    "params": {
      1: "0.5 0.1 0.0 0.0 100.0 100.0",   # nH
      2: "0.151 -0.01 0.0 0.0 10.0 10.0",    # Redshift ★追加
      3: "1.5 0.1 -2.0 -2.0 5.0 5.0",     # Gamma
      4: "1.0 1.0 0.1 0.1 500.0 500.0",   # HighECut
      5: "2.0 0.01 0.0 0.0 1e10 1e10"     # Norm
    }
  }
}

#======================

os.makedirs(OUTPUT_DIR, exist_ok=True)

if only_model is not None:
  if type(only_model) is not list:
    print(f"ERROR: 'only_model' must be a list of model names or None. Found type: {type(only_model).__name__}")
    sys.exit(1)
  for model_name in only_model:
    if model_name not in MODELS.keys():
      print(f"WARNING: Model '{model_name}' specified in 'only_model' is not defined in MODELS.")
      print(f"Available models are: {', '.join(MODELS.keys())}")
      sys.exit(1)

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
  if tf_eeufspec:
    xspec.Plot("eeufspec")
  elif not tf_eeufspec:
    xspec.Plot.area = True
    xspec.Plot("data")
  
  m_vals = xspec.Plot.model()
  
  return m, chi2, red_chi2, m_vals

def treat_data(s):
  xspec.Plot.xAxis = "keV"
  if tf_eeufspec:
    print("Defining dummy model for unfolding...")
    m_dummy = xspec.Model("powerlaw")
    m_dummy.powerlaw.PhoIndex = 2.0
    m_dummy.powerlaw.norm = 1.0
    xspec.Plot("eeufspec")
  elif not tf_eeufspec:
    xspec.Plot.area = True
    xspec.Plot("data")
  
  x_vals = xspec.Plot.x()
  x_err = xspec.Plot.xErr()
  y_net = xspec.Plot.y()
  y_err = xspec.Plot.yErr()
  
  xspec.Plot.xAxis = "keV"
  xspec.Plot('Background')
  y_bkg  = xspec.Plot.y()
  
  y_tot = [n + b for n, b in zip(y_net, y_bkg)]
  
  xspec.AllModels.clear()
  
  return x_vals, x_err, y_net, y_err, y_bkg, y_tot

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [2, 1]}, constrained_layout=True)
plt.subplots_adjust(hspace=0.0)

for bkgtype in ["3c50", "scorpion"]:
  if bkgtype=="scorpion":
    if tf_scorpion:
      pass
    else:
      continue
  x_vals, x_err, y_net, y_err, y_bkg, y_tot = treat_data(load_data(ObsID, bkgtype))
  
  ax1.errorbar(x_vals, y_tot, fmt='.', label=f'Total({bkgtype})', alpha=0.3)
  ax1.errorbar(x_vals, y_net, yerr=0, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
  #ax1.errorbar(x_vals, y_net, yerr=y_err, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
  ax1.step(x_vals, y_bkg, where='mid', label=f'Background({bkgtype})', alpha=0.3)
  
  for i, (name, config) in enumerate(MODELS.items()):
    if only_model == None:
      pass
    else:
      if name not in only_model:
        continue
    
    m, chi2, red_chi2, m_vals = run_fit(config)
    
    print(f"[{name}] Red.Chi2: {red_chi2:.2f}")
    
    if max(m_vals) > 0:
      ax1.plot(x_vals, m_vals, label=f'{name}({bkgtype})($\chi^2_\\nu$={red_chi2:.2f})', linewidth=2)
    
    residuals = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y_net, m_vals, y_err)]
    ax2.errorbar(x_vals, residuals, fmt='.', alpha=0.6, label=f"Residuals({bkgtype})({name})")
    
    row_data = list(zip(*[x_vals, y_tot, y_net, m_vals, y_err]))
    with open(f'{OUTPUT_DIR}/{ObsID}_{bkgtype}_{name}.csv', 'w', newline='') as f:
      writer = csv.writer(f)
      writer.writerow(['x_vals', 'y_tot', 'y_net', 'm_vals', 'y_err'])
      writer.writerows(row_data)

fig.suptitle(f'GRB221009A NICER Spectrum Fit:ObsID{ObsID}')

ax1.set_xscale('log')
ax1.set_yscale('log')

if tf_eeufspec:
  ax1.set_ylabel(r'Energy Flux ($E^2 F_E$) [$\mathrm{erg \cdot cm^2\cdot s^{-1}}$]')
elif not tf_eeufspec:
  ax1.set_ylabel(r'Counts s$^{-1}$ keV$^{-1}$')

ax1.legend(framealpha=0.1, bbox_to_anchor=(1.05, 1), loc='upper left')
ax1.grid(True, which="both", ls="--", alpha=0.3)

ax2.axhline(0,color="black", linestyle='--', alpha=0.5)
ax2.set_xscale('log')
ax2.set_ylabel('(Data-Model)/Error')
ax2.set_xlabel('Energy (keV)')
#ax2.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
ax2.legend(framealpha=0.1, bbox_to_anchor=(1.05, 1), loc='upper left')
ax2.grid(True, which="both", ls=":", alpha=0.5)

option_figure_name=[]

if tf_eeufspec:
  option_figure_name.append("_eeufspec")
elif not tf_eeufspec:
  option_figure_name.append("_plot")

if tf_scorpion:
  option_figure_name.append("_withScorpion")
elif not tf_scorpion:
  option_figure_name.append("_noScorpion")

figure_name = str(ObsID)
for option in option_figure_name:
  figure_name += option

figure_path = os.path.join(OUTPUT_DIR, figure_name)

fig.savefig(figure_path)
print(f"\nグラフを '{figure_path}' に保存しました。")