import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import sys
from scripts.utils.read_config import cfg
import subprocess
import re

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

# 設定からパスなどを取得

#norm_list = [7.5e-5, 1.2e-4, 4e-4]
norm_list = [0.012]

file_name = cfg['spectrum']['path']['merge_name']
file_path = os.path.join(cfg['spectrum']['path']['merge_output'], file_name)

grp_time = cfg['spectrum']['parameters']['grp_time']
ignoreRange = cfg['spectrum']['parameters']['ignoreRange']

# check_detection_limit内で使用されるグローバル変数
OUTPUT_DIR = f"results/spectrum/{file_name}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

limit_dir = os.path.join(OUTPUT_DIR, "limit_results")
os.makedirs(limit_dir, exist_ok=True)

# Scorpion等の設定フラグ
tf_scorpion = False

MODELS = {
    "ZPL": {
      "expr": "tbabs * ztbabs * powerlaw",
      "params": {
        1: "0.538 -1 0.0 0.0 100.0 100.0",
        2: "1.29",
        3: "0.151 -1 0.0 0.0 10.0 10.0",
        4: "1.8 0.1 -2.0 -2.0 5.0 5.0",
        5: "1.0 0.01 0.0 0.0 1e10 1e10"
      }
    },
    "ZPL+Fe": {
      "expr": "tbabs * ztbabs * (powerlaw + gauss)",
      "params": {
        1: "0.538 -1",
        2: "1.29",
        3: "0.151 -1",
        4: "1.8 0.1 -2.0 -2.0 5.0 5.0",
        5: "1.0 0.1 0.0 0.0 1e10 1e10",
        6: "5.560 -1",
        7: "1.0e-5 -1",
        8: "0 0.1 -1e10 -1e10 1e10 1e10"
      }
    }
}

def setup_model(model_config):
  xspec.AllModels.clear()
  m = xspec.Model(model_config['expr'])
  for idx, val_str in model_config['params'].items():
    m(idx).values = val_str
  return m


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

  print("\n--- Calculating Errors (90% confidence) ---")
  try:
    free_params = [i for i in range(1, m.nParameters+1) if not m(i).frozen]
    xspec.Fit.error("2.706 " + " ".join(map(str, free_params)))
  except Exception as e:
    print(f"Error calculation failed: {e}")

  pho_index = m.powerlaw.PhoIndex.values[0]
  pho_err_low = m.powerlaw.PhoIndex.error[0]
  pho_err_high = m.powerlaw.PhoIndex.error[1]
  print(f"Photon Index: {pho_index:.4f} (-{pho_index-pho_err_low:.4f}, +{pho_err_high-pho_index:.4f})")

  chi2 = xspec.Fit.statistic
  dof = xspec.Fit.dof
  red_chi2 = chi2 / dof if dof > 0 else 0

  xspec.Plot.xAxis = "keV"
  xspec.Plot.add = True
  xspec.Plot("data")

  m_vals = xspec.Plot.model()

  def output_eq():
    log_file = "xspec_temp_log_for_eq.txt"

    if os.path.exists(log_file):
      os.remove(log_file)

    xspec.Xset.openLog(log_file)
    xspec.Xset.logChatter = 10

    try:
      xspec.AllModels.eqwidth(4, err=True, number=1000, level=90)
    finally:
      xspec.Xset.closeLog()

    with open(log_file, "r") as f:
      output = f.read()

    val_match = re.search(r"equiv width for Component \d+:\s+([\d\.eE+-]+)\s+keV", output)
    # 例: Equiv width error range:  0.0743171 - 0.267984 keV
    err_match = re.search(r"error range:\s+([\d\.eE+-]+)\s+-\s+([\d\.eE+-]+)\s+keV", output)

    if val_match:
      print(f"抽出された値: {val_match.group(1)}")
      val_match = val_match.group(1)
    if err_match:
      print(f"抽出された誤差範囲: {err_match.group(1)} to {err_match.group(2)}")
      err_match = [err_match.group(1), err_match.group(2)]

    print(f"{val_match=}", f"{err_match=}")

    os.remove(log_file)

    return val_match, err_match

  if model_config['expr'] == "tbabs * ztbabs * (powerlaw + gauss)":
    eq_val, eq_err = output_eq()
  else:
    eq_val, eq_err = None, [None, None]

  return m, chi2, dof, red_chi2, m_vals, eq_val, eq_err

def real_plot(cfg):
  # --- Step 0: 準備 (File Link & Path) ---
  data_dir = os.path.abspath(os.path.join(cfg['spectrum']['path']['merge_output'], cfg['spectrum']['path']['merge_name']))

  xspec.AllData.clear()

  current_dir = os.getcwd()
  try:
    os.chdir(file_path)
    xspec.AllData(f"1:1 {os.path.join(data_dir, file_name)}_grp.pha")
  finally:
    os.chdir(current_dir)

  xspec.AllData(1).ignore(ignoreRange)

  xspec.Plot.xAxis = "keV"
  xspec.Plot('data')

  x_vals = xspec.Plot.x()
  x_err = xspec.Plot.xErr()
  y_net = xspec.Plot.y()
  y_err = xspec.Plot.yErr()

  ax1_spec.errorbar(x_vals, y_net, xerr=x_err, yerr=y_err, fmt='.', label=f'Observed', alpha=0.3)

def fake_plot(cfg, test_norm, base_config, comp_config, spectrum_obj):

  # --- Step 0: 準備 (File Link & Path) ---
  data_dir = os.path.abspath(os.path.join(cfg['spectrum']['path']['merge_output'], cfg['spectrum']['path']['merge_name']))

  rmf = spectrum_obj.response.rmf
  if not os.path.isabs(rmf): rmf = os.path.join(data_dir, rmf)

  bkg = spectrum_obj.background.fileName
  if not os.path.isabs(bkg): bkg = os.path.join(data_dir, bkg)

  arf = ""
  try:
    if spectrum_obj.response.arf:
      arf = spectrum_obj.response.arf
      if not os.path.isabs(arf): arf = os.path.join(data_dir, arf)
  except:
    pass

  exposure = spectrum_obj.exposure

  # ベースライン（連続成分）のパラメータを決定するために一度Fit
  current_dir = os.getcwd()
  try:
    os.chdir(file_path)

    xspec.AllData.clear()
    xspec.AllData(f"1:1 {os.path.join(data_dir, file_name)}_grp.pha")
    xspec.AllData(1).ignore(ignoreRange)
    m_base_real = setup_model(base_config)
    xspec.Fit.perform()

    best_continuum_params = []
    for i in range(1, m_base_real.nParameters + 1):
      best_continuum_params.append(m_base_real(i).values)
  finally:
    os.chdir(current_dir)

  xspec.AllData.clear()
  xspec.AllModels.clear()

  m_inj = xspec.Model(comp_config['expr'])

  for idx, val_str in comp_config['params'].items():
    m_inj(idx).values = val_str

  # 連続成分を実データのベストフィットに合わせる
  param_idx = 1
  for val_str in best_continuum_params:
    if param_idx <= len(best_continuum_params):
      m_inj(param_idx).values = val_str
    param_idx += 1

  # 鉄輝線のNormをテスト値に固定してInjection
  # ※パラメータ番号8がNormである前提 (ZPL+Feモデル)
  gauss_norm_idx = 8
  m_inj(gauss_norm_idx).values = test_norm
  m_inj(gauss_norm_idx).frozen = True

  fake_name = f"temp_limit"

  # --- 2. Fakeit (スペクトル生成) ---
  fs = xspec.FakeitSettings(response=rmf, arf=arf, background=bkg, exposure=exposure, correction=1.0, fileName=fake_name+".fak")
  xspec.AllData.fakeit(1, fs, applyStats=True, filePrefix="")

  # --- 3. grppha (グルーピング) ---
  out_grp_name = f"{fake_name}_grp.pha"
  if os.path.exists(out_grp_name):
    os.remove(out_grp_name)

  grppha_input = (
    f"chkey BACKFILE {fake_name}_bkg.fak\n"
    f"chkey RESPFILE {rmf}\n"
    f"group min {grp_time}\n"
    f"exit\n"
  )
  subprocess.run(
    ["grppha", f"infile={fake_name}.fak", f"outfile={out_grp_name}", "clobber=yes"], input=grppha_input, text=True, stdout=subprocess.DEVNULL, check=True
  )

  xspec.AllData.clear()
  xspec.AllData(f"1:1 {out_grp_name}")
  xspec.AllData(1).ignore(ignoreRange)

  xspec.Plot.xAxis = "keV"
  xspec.Plot('data')

  x_vals = xspec.Plot.x()
  x_err = xspec.Plot.xErr()
  y_net = xspec.Plot.y()
  y_err = xspec.Plot.yErr()

  ax1_spec.errorbar(x_vals, y_net, xerr=x_err, yerr=y_err, fmt='.', label=f'Injected(norm:{test_norm:.1e})', alpha=0.3)

  #Delta chi2の導出
  _, chi2_base, _, _, _, _, _ = run_fit(MODELS["ZPL"])
  m_comp, chi2_comp, _, _, _, _, _ = run_fit(MODELS["ZPL+Fe"])

  print(f"Gaussian Norm Status: {m_comp(8).frozen}")

  del_chi2 = chi2_base - chi2_comp

  print(f"{del_chi2=}")

if __name__ == "__main__":
  # 追加: XSPEC設定 (メインプロセス)
  xspec.Fit.query = "yes"

  # データをロードするための準備
  print(f"Loading data from: {file_path}")
  obs_directory = file_path
  data_filename = f"{file_name}_grp.pha"
  bkg_filename = f"{file_name}_bkg_3c50.pha"

  current_dir = os.getcwd()

  fig_spec, ax1_spec = plt.subplots(1, 1, figsize=(10, 6), constrained_layout=True)

  real_plot(cfg)

  for test_norm in norm_list:
    # Spectrumオブジェクトの作成
    try:
      if not os.path.exists(obs_directory):
        print(f"ERROR: Directory not found: {obs_directory}")
        sys.exit(1)

      os.chdir(obs_directory)

      if not os.path.exists(data_filename):
        print(f"ERROR: Data file not found: {data_filename}")
        sys.exit(1)

      s = xspec.Spectrum(data_filename)
      s.background = bkg_filename

      if s.response is None or s.response.rmf == "":
        rsp_file = f"{file_name}.rsp"
        if os.path.exists(rsp_file):
          s.response = rsp_file

      print(f"Loaded: {s.fileName}")

    finally:
      os.chdir(current_dir)
      fake_plot(
        cfg,
        test_norm,
        MODELS["ZPL"],
        MODELS["ZPL+Fe"],
        s
      )

  ax1_spec.axvline(5.560, linestyle='--', color="black", label="Fe(E=5.560 keV)")

  ax1_spec.set_xlabel('Energy (keV)')
  ax1_spec.set_ylabel(r'Counts s$^{-1}$ keV$^{-1}$')

  ax1_spec.set_xscale('log')
  ax1_spec.set_yscale('log')
  ax1_spec.set_xlim(4.8, 6.5)
  ax1_spec.set_ylim(10, 100)
  ax1_spec.grid(True, which="both", ls=":", alpha=0.5)

  ax1_spec.legend()

  figure_path = os.path.join(OUTPUT_DIR, f"{file_name}_normfikeit.png")
  fig_spec.savefig(figure_path)