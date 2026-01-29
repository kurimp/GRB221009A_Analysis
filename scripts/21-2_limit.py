import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import os
import csv
import sys
from scripts.utils.read_config import cfg
import datetime
import scipy.stats
import numpy as np
import shutil
from tqdm import tqdm
import subprocess
import pandas as pd
import glob
import re
import concurrent.futures
import random

# 設定からパスなどを取得
file_name = cfg['spectrum']['path']['merge_name']
file_path = os.path.join(cfg['spectrum']['path']['merge_output'], file_name)

grp_time = cfg['spectrum']['parameters']['grp_time']
ignoreRange = cfg['spectrum']['parameters']['ignoreRange']

n_limit = cfg['spectrum']['parameters']['limit']['n']
threshold_ratio = cfg['spectrum']['parameters']['limit']['threshold_ratio(%)']
detected_ratio = cfg['spectrum']['parameters']['limit']['detected_ratio(%)']
norm_pointed = cfg['spectrum']['parameters']['limit']['norm_pointed']
bases = cfg['spectrum']['parameters']['limit']['bases']
exp_start = cfg['spectrum']['parameters']['limit']['exponents'][0]
exp_end = cfg['spectrum']['parameters']['limit']['exponents'][1]

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

def generate_custom_norms():
  if norm_pointed == 'None':
    exponents = range(exp_start, exp_end)

    norm_list = []
    for e in exponents:
      for b in bases:
        val = b * (10 ** e)
        if val <= 10000000:
          norm_list.append(val)

    norm_list = sorted(list(set(norm_list)))

  else:
    norm_list = norm_pointed

  return norm_list

def limit_worker(args):
  (iter_idx, test_norm, base_config, comp_config, rmf, arf, bkg, exposure, grp_time, ignoreRange, file_path, best_continuum_params, threshold_chi2) = args

  pid = os.getpid()

  temp_pfiles_dir = os.path.join(file_path, f"pfiles_{pid}")
  os.makedirs(temp_pfiles_dir, exist_ok=True)

  if "HEADAS" in os.environ:
    sys_pfiles = os.path.join(os.environ["HEADAS"], "syspfiles")
    os.environ["PFILES"] = f"{temp_pfiles_dir};{sys_pfiles}"
  else:
    os.environ["PFILES"] = f"{temp_pfiles_dir};/usr/local/headas/syspfiles"

  fake_name = f"temp_limit_{pid}_{iter_idx}"

  work_dir = os.path.join(file_path, "limit_temp_parallel")
  os.makedirs(work_dir, exist_ok=True)

  import xspec
  xspec.Xset.chatter = 0
  xspec.Xset.logChatter = 0
  xspec.Fit.query = "yes"

  #乱数付与
  MAX_INT = 2147483647
  unique_seed = int((pid * 10000 + iter_idx) % MAX_INT)
  if unique_seed == 0: unique_seed = 1

  xspec.Xset.seed = unique_seed

  np.random.seed(unique_seed)
  random.seed(unique_seed)

  current_dir = os.getcwd()
  os.chdir(work_dir)

  is_detected = False

  try:
    xspec.AllData.clear()
    xspec.AllModels.clear()

    #信号入りモデルの作成
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

    # --- 4. Fit & Recovery Check ---
    xspec.AllData.clear()
    xspec.AllData(f"1:1 {out_grp_name}")
    xspec.AllData(1).ignore(ignoreRange)

    # A. Base Model (Line無し) Fit
    xspec.AllModels.clear()
    m_base = xspec.Model(base_config['expr'])

    for idx, val_str in base_config['params'].items():
      m_base(idx).values = val_str

    param_idx = 1
    for val in best_continuum_params:
      if param_idx <= m_base.nParameters:
        m_base(param_idx).values = val
      param_idx += 1

    xspec.Fit.renorm()
    xspec.Fit.perform()
    chi2_base = xspec.Fit.statistic

    # B. Comp Model (Line有り) Fit
    xspec.AllModels.clear()
    m_comp = xspec.Model(comp_config['expr'])
    for idx, val_str in comp_config['params'].items():
      m_comp(idx).values = val_str

    param_idx = 1
    for val in best_continuum_params:
      if param_idx <= m_comp.nParameters:
        m_comp(param_idx).values = val
      param_idx += 1

    # NormをFreeにして「見つかるか」を試す
    step_size = test_norm / 10.0 if test_norm > 0 else 1e-4
    m_comp(gauss_norm_idx).values = f"{test_norm} {step_size} -1e10 -1e10 1e10 1e10"
    m_comp(gauss_norm_idx).frozen = False

    xspec.Fit.renorm()
    xspec.Fit.perform()
    chi2_comp = xspec.Fit.statistic

    # --- 5. 判定 ---
    d_chi2 = chi2_base - chi2_comp

    if d_chi2 > threshold_chi2:
      is_detected = True

    result = (is_detected, d_chi2)
  except Exception as e:
    # エラー時は検出失敗扱い
    result = (False, None)
  finally:
    # クリーンアップ
    for f in glob.glob(f"{fake_name}*"):
      try: os.remove(f)
      except: pass
    os.chdir(current_dir)
  return result

def check_detection_limit(cfg, target_norm_list, base_config, comp_config, spectrum_obj, n_sim, sim_delta_chi2_array=None):
  """
  指定したNormのリストに対して、どれくらいの確率で検出できるか（感度）を調べる
  """
  print(f"\n=== Starting Detection Limit Check (Sensitivity Analysis) ===")

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

  # --- Step 1: 閾値の決定 (Null Simulation結果の読み込み) ---
  mc_output_dir = os.path.join(OUTPUT_DIR, "mc_results")
  list_candidate_file  = sorted(glob.glob(os.path.join(mc_output_dir, "seglist_*_mc_*.csv")))

  try:
    latest_file = max(
      list_candidate_file,
      key=lambda f: int(re.search(r'mc_([0-9]+)', os.path.basename(f)).group(1)) if re.search(r'mc_([0-9]+)', os.path.basename(f)) else 0
    )
    print(f"Using Null MC Result: {os.path.basename(latest_file)}")
    mc_data = pd.read_csv(latest_file)

    null_delta_chi2 = np.array(mc_data['Simulated_Delta_Chi2'])
    threshold_chi2 = np.percentile(null_delta_chi2, threshold_ratio)
    print(f"Detection Threshold ({threshold_ratio}%): Delta Chi2 > {threshold_chi2:.2f}")
  except Exception as e:
    print(f"データ読み込みエラー: {e}")
    return None

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

  # --- Step 2: 各Normでの検出率調査 (Signal Simulation) ---
  results_norm = []
  results_prob = []

  # 並列化用のワーカー数決定
  num_cores = os.cpu_count()
  use_workers = max(1, num_cores - 1)

  print(f"\nStarting Signal Injection Loop (Parallelized with {use_workers} cores)...")

  d_chi2_records = []

  # Normごとのループはシリアルのまま（早期終了判定のため）
  for test_norm in target_norm_list:
    test_norm = float(test_norm)
    # Workerに渡す引数のリストを作成 (N=n_sim個)
    worker_args = []
    for i in range(n_sim):
      worker_args.append((
        i, test_norm, base_config, comp_config, rmf, arf, bkg, exposure,
        cfg['spectrum']['parameters']['grp_time'],
        cfg['spectrum']['parameters']['ignoreRange'],
        data_dir, best_continuum_params, threshold_chi2
      ))

    # 並列実行
    results_d_chi2 = []
    results_detected = []
    pass_count = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=use_workers) as executor:
      # tqdmで進捗表示
      results = list(tqdm(executor.map(limit_worker, worker_args), total=n_sim, desc=f"Norm={test_norm:.1e}", leave=False))

    for res in results:
      results_detected.append(res[0])
      results_d_chi2.append(res[1])
      d_chi2_records.append({
        "Norm": test_norm,
        "Delta_Chi2": res[1]
      })

    # 結果集計 (Trueの数をカウント)
    pass_count = sum(results_detected)

    detection_prob = pass_count / n_sim
    results_norm.append(test_norm)
    results_prob.append(detection_prob)

    print(f"  Norm: {test_norm:.2e} -> Prob: {detection_prob*100:.1f}%")

    # 100%検出が続いたらループを抜ける（時短）
    if len(results_prob) > 5 and all(p >= 1 for p in results_prob[-5:]):
      print("  Reached 100% detection. Stopping loop.")
      break

  #d_chi2をcsvに保存
  df_all_dchi2 = pd.DataFrame(d_chi2_records)
  limit_d_chi2_csv_path = os.path.join(limit_dir, f"{file_name}_limit_{n_sim}.csv")
  df_all_dchi2.to_csv(limit_d_chi2_csv_path, index=False)
  print(f"Saved All Simulation Details: {limit_d_chi2_csv_path}")

  # CSV保存
  df_res = pd.DataFrame({"Norm": results_norm, "Probability": results_prob})
  csv_save_path = os.path.join(limit_dir, f"{file_name}_sensitivity_details.csv")
  df_res.to_csv(csv_save_path, index=False)
  print(f"\nSaved Sensitivity Data: {csv_save_path}")

  # プロット作成
  plt.figure(figsize=(8, 6))
  plt.plot(results_norm, results_prob, 'o-', color='navy', label='Detection Probability')

  for ratio in detected_ratio:
    plt.axhline(ratio/100, linestyle='--', label=rf'Detection rate: {ratio}% Confidence')

  plt.xscale('log')
  plt.xlabel('Injected Fe Line Norm')
  plt.ylabel('Detection Probability')
  plt.ylim(-0.1, 1.1)
  plt.title(f'Sensitivity Curve: {file_name}\n(Threshold $\Delta\chi^2$ > {threshold_chi2:.2f})')
  plt.grid(True, which="both", ls="--", alpha=0.3)
  plt.legend()

  plot_save_path = os.path.join(limit_dir, f"{file_name}_sensitivity_curve_details_{n_limit}.png")
  plt.savefig(plot_save_path)
  plt.close()
  print(f"Saved Sensitivity Plot: {plot_save_path}")

  return results_norm, results_prob

if __name__ == "__main__":
  # 追加: XSPEC設定 (メインプロセス)
  xspec.Fit.query = "yes"

  # データをロードするための準備 (run_spectrum_analysis内の一部を再現)
  print(f"Loading data from: {file_path}")
  obs_directory = file_path
  data_filename = f"{file_name}_grp.pha"
  bkg_filename = f"{file_name}_bkg_3c50.pha"

  current_dir = os.getcwd()

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

  # 感度解析の実行
  target_norm_list = generate_custom_norms()

  check_detection_limit(
    cfg,
    target_norm_list,
    MODELS["ZPL"],
    MODELS["ZPL+Fe"],
    s,
    n_sim=n_limit
  )