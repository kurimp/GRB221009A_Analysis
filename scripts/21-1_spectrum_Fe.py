import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import os
import csv
import sys
from scripts.utils.read_config import cfg as default_cfg
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

def mc_worker(args):
  (iter_idx, base_config, comp_config, rmf, arf, bkg, exposure, grp_time, ignoreRange, file_path, best_params_base) = args

  pid = os.getpid()

  temp_pfiles_dir = os.path.join(file_path, f"pfiles_{pid}")
  os.makedirs(temp_pfiles_dir, exist_ok=True)

  if "HEADAS" in os.environ:
    sys_pfiles = os.path.join(os.environ["HEADAS"], "syspfiles")
    os.environ["PFILES"] = f"{temp_pfiles_dir};{sys_pfiles}"
  else:
    os.environ["PFILES"] = f"{temp_pfiles_dir};/usr/local/headas/syspfiles"

  fake_name = f"temp_mc_{pid}_{iter_idx}"

  work_dir = os.path.join(file_path, "mc_temp_parallel")
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

  result = None

  try:
    #xspecの情報を初期化
    xspec.AllData.clear()
    xspec.AllModels.clear()

    #輝線なしのmodelの読み込みとfitパラメータの代入
    m_temp = xspec.Model(base_config['expr'])
    for idx, values in enumerate(best_params_base):
      m_temp(idx + 1).values = values

    #fakeit
    fs = xspec.FakeitSettings(response=rmf, arf=arf, background=bkg, exposure=exposure, correction=1.0, fileName=fake_name+".fak")
    xspec.AllData.fakeit(1, fs, applyStats=True, filePrefix="")

    #grppha
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

    #fitの実行
    xspec.AllData.clear()
    xspec.AllData(f"1:1 {out_grp_name}")
    xspec.AllData(1).ignore(ignoreRange)

    #fakeitデータへの輝線なしmodelでのfit
    m_base = xspec.Model(base_config['expr'])
    for idx, val_str in base_config['params'].items():
      m_base(idx).values = val_str
    xspec.Fit.perform()
    chi2_base = xspec.Fit.statistic
    dof_base = xspec.Fit.dof

    #fakeitデータへの輝線ありmodelでのfit
    m_comp = xspec.Model(comp_config['expr'])
    for idx, val_str in comp_config['params'].items():
      m_comp(idx).values = val_str
    xspec.Fit.perform()
    chi2_comp = xspec.Fit.statistic
    dof_comp = xspec.Fit.dof

    d_chi2 = chi2_base - chi2_comp
    d_dof = dof_base - dof_comp

    f_val = (d_chi2 / d_dof) / (chi2_comp / dof_comp) if (d_dof > 0 and dof_comp > 0) else 0.0

    # 結果を格納
    result = (d_chi2, f_val)
  except Exception:
    result = None
  finally:
    for f in glob.glob(f"{fake_name}*"):
        try: os.remove(f)
        except: pass
    os.chdir(current_dir)
  return result

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

    # --- 1. 信号入りモデルの作成 (Injection) ---
    m_inj = xspec.Model(comp_config['expr'])

    for idx, val_str in comp_config['params'].items():
      m_inj(idx).values = val_str

    # 連続成分を実データのベストフィットに合わせる
    param_idx = 1
    for val in best_continuum_params:
      if param_idx <= m_inj.nParameters:
        m_inj(param_idx).values = val
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

    if iter_idx == 0: # 最初の1回だけ詳細表示
      print(f"[DEBUG] PID={os.getpid()} Seed={unique_seed}")
      print(f"[DEBUG] Base Chi2={chi2_base:.4f}, Comp Chi2={chi2_comp:.4f}, dChi2={d_chi2:.4f}")
      print(f"[DEBUG] Threshold={threshold_chi2:.4f}")

    if d_chi2 > threshold_chi2:
      is_detected = True

  except Exception as e:
    # エラー時は検出失敗扱い
    is_detected = False
  finally:
    # クリーンアップ
    for f in glob.glob(f"{fake_name}*"):
      try: os.remove(f)
      except: pass
    os.chdir(current_dir)
  return is_detected

def run_spectrum_analysis(cfg):
  import xspec
  xspec.Fit.query = "yes"
  #===========config===========
  #plotのy軸表記選択。FluxならTrue。
  tf_eeufspec = False

  #使用するObsIDを選択。
  file_name = cfg['spectrum']['path']['merge_name']
  file_path = os.path.join(cfg['spectrum']['path']['merge_output'], file_name)

  #scorpionでのbackgroundを扱うかどうかを選択。使うならTrue。
  tf_scorpion = False

  #モンテカルロシミュレーションの実行の如何
  is_mc = cfg['spectrum']['parameters']['mc']['is']
  n_mc = cfg['spectrum']['parameters']['mc']['n']

  #検出限界検定の実行の如何
  is_limit = cfg['spectrum']['parameters']['limit']['is']
  n_limit = cfg['spectrum']['parameters']['limit']['n']

  systematic = cfg['spectrum']['parameters']['systematic']
  ignoreRange = cfg['spectrum']['parameters']['ignoreRange']

  #特定のモデルのみ処理を実施したい場合、モデル名をlistで与える。なければNone。
  only_model = cfg['spectrum']['parameters']['only_model']

  grp_time = cfg['spectrum']['parameters']['grp_time']

  OUTPUT_DIR = f"results/spectrum/{file_name}"

  # 比較したいモデルのリスト
  # "モデル名": { "expr": "XSPECの式", "params": { パラメータ番号: "初期値設定文字列" } }
  MODELS = {
    "ZPL": {
      "expr": "tbabs * ztbabs * powerlaw",
      "params": {
        # 1: tbabs (Galactic nH) -> 5.38e21 cm^-2 = 0.538
        1: "0.538 -1 0.0 0.0 100.0 100.0",
        # 2: ztbabs (Intrinsic nH) -> 1.29e22 cm^-2 = 1.29
        2: "1.29",
        # 3: ztbabs (Redshift)
        3: "0.151 -1 0.0 0.0 10.0 10.0",
        # 4: powerlaw (Photon Index) -> 自由
        4: "1.8 0.1 -2.0 -2.0 5.0 5.0",
        # 5: powerlaw (Norm) -> 自由
        5: "1.0 0.01 0.0 0.0 1e10 1e10"
      }
    },
    "ZPL+Fe": {
      "expr": "tbabs * ztbabs * (powerlaw + gauss)",
      "params": {
        # 1: ztbabs (Galactic nH)
        1: "0.538 -1",
        # 2: ztbabs (Intrinsic nH)
        2: "1.29",
        # 3: ztbabs (Redshift)
        3: "0.151 -1",
        # 4: powerlaw (Photon Index)
        4: "1.8 0.1 -2.0 -2.0 5.0 5.0",
        # 5: powerlaw (Norm)
        5: "1.0 0.1 0.0 0.0 1e10 1e10",
        # 6: gauss (LineE)
        6: "5.560 -1",
        # 7: gauss (Sigma)
        7: "1.0e-5 -1",
        # 8: gauss (Norm)
        8: "0 0.1 -1e10 -1e10 1e10 1e10"
      }
    }
  }

  os.makedirs(OUTPUT_DIR, exist_ok=True)

  if only_model is not None:
    if type(only_model) is not list:
      print(f"ERROR: 'only_model' must be a list of model names or None. Found type: {type(only_model).__name__}")
      sys.exit(1)
    for model_name in list(MODELS.keys()):
      if model_name not in only_model:
        del MODELS[model_name]
    for model_name in only_model:
      if model_name not in MODELS.keys():
        print(f"WARNING: Model '{model_name}' specified in 'only_model' is not defined in MODELS.")
        print(f"Available models are: {', '.join(MODELS.keys())}")
        sys.exit(1)

  def load_data(file_name, bkgtype="3c50"):
    xspec.AllData.clear()
    xspec.AllModels.clear()

    xspec.Fit.statMethod = "chi"
    obs_directory = file_path
    data_filename = f"{file_name}_grp.pha"


    if bkgtype == "3c50":
      bkg_filename = f"{file_name}_bkg_3c50.pha"
    else:
      print("bkgtype must be either '3c50' or 'scorpion'.")

    current_dir = os.getcwd()

    try:
      if not os.path.exists(obs_directory):
        print(f"ERROR: Directory not found: {obs_directory}")
        return None

      os.chdir(obs_directory)

      if not os.path.exists(data_filename):
        print(f"ERROR: Data file not found: {data_filename}")
        return None

      s = xspec.Spectrum(data_filename)
      print(f"Original Bins: {len(xspec.AllData(1).values)}")
      s.background = bkg_filename

      if s.response is None or s.response.rmf == "":
        print("Response not loaded automatically. Trying manual load...")
        rsp_file = f"{file_name}.rsp"
        if os.path.exists(rsp_file):
          s.response = rsp_file
        else:
          print(f"Error: Response file {rsp_file} not found.")

      print(f"Loaded: {s.fileName}")

      s.ignore(ignoreRange)

      return s

    except Exception as e:
      print(f"データ読み込みエラー: {e}")
      return None
    finally:
      os.chdir(current_dir)

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
    if tf_eeufspec:
      xspec.Plot("eeufspec")
    elif not tf_eeufspec:
      #xspec.Plot.area = True
      xspec.Plot("data")

    m_vals = xspec.Plot.model()

    return m, chi2, dof, red_chi2, m_vals

  def treat_data(s):
    xspec.Plot.xAxis = "keV"
    if tf_eeufspec:
      print("Defining dummy model for unfolding...")
      m_dummy = xspec.Model("powerlaw")
      m_dummy.powerlaw.PhoIndex = 2.0
      m_dummy.powerlaw.norm = 1.0
      xspec.Plot("eeufspec")
    elif not tf_eeufspec:
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

  def run_monte_carlo(base_config, comp_config, real_delta_chi2, real_f_val, delta_dof, n_sim, spectrum_obj):
    print(f"\n=== Starting Monte Carlo Simulation (N={n_sim}) ===")

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

    # BaseモデルのBestFitパラメータを取得（Fakeitの種）

    xspec.AllData(1).ignore(cfg['spectrum']['parameters']['ignoreRange'])
    m_base = setup_model(base_config)
    xspec.Fit.perform()
    best_params_base = [m_base(i).values for i in range(1, m_base.nParameters + 1)]

    worker_args = []
    for i in range(n_sim):
      worker_args.append((
        i, base_config, comp_config, rmf, arf, bkg, exposure,
        cfg['spectrum']['parameters']['grp_time'],
        cfg['spectrum']['parameters']['ignoreRange'],
        data_dir, best_params_base
      ))

    sim_delta_chi2_list = []
    sim_f_list = []

    num_cores = os.cpu_count()  # CPUの論理コア数を取得
    use_workers = max(1, num_cores - 1)  # 2つだけ予備に残しておく

    with concurrent.futures.ProcessPoolExecutor(max_workers=use_workers) as executor:
      # tqdmで進捗表示
      results = list(tqdm(executor.map(mc_worker, worker_args), total=n_sim))

    for res in results:
      if res is not None:
        sim_delta_chi2_list.append(res[0])
        sim_f_list.append(res[1])

    # 集計処理
    success_count = len(sim_delta_chi2_list)
    if success_count == 0:
      return None, None, None # 戻り値を変更

    sim_delta_chi2_array = np.array(sim_delta_chi2_list)
    sim_f_array = np.array(sim_f_list)

    # p値計算
    n_greater = np.sum(sim_f_array >= real_f_val)
    p_val_mc = (n_greater + 1) / (success_count + 1)

    # 閾値（95%点）の計算（Limit Check用に返す）
    threshold_90 = np.percentile(sim_delta_chi2_array, 90)
    threshold_95 = np.percentile(sim_delta_chi2_array, 95)
    threshold_99 = np.percentile(sim_delta_chi2_array, 99)

    print(f"MC P-value: {p_val_mc:.4f}")
    print(f"Thresholds -> 90%: {threshold_90:.2f}, 95%: {threshold_95:.2f}, 99%: {threshold_99:.2f}")

    sim_spectra_y = []
    sim_spectra_x = []

    if success_count == 0:
      return None

    sim_delta_chi2_array = np.array(sim_delta_chi2_list)
    sim_f_array = np.array(sim_f_list)

    n_greater = np.sum(sim_f_array >= real_f_val)
    p_val_mc = (n_greater + 1) / (success_count + 1)

    mc_output_dir = os.path.join(OUTPUT_DIR, "mc_results")
    os.makedirs(mc_output_dir, exist_ok=True)

    if len(sim_spectra_y) > 0:
      plt.figure(figsize=(10, 7))

      X_flat = []
      Y_flat = []

      # 【修正点2】保存したリストをzipで回して、個別にペアにする
      for x_vals, y_vals in zip(sim_spectra_x, sim_spectra_y):
        x_arr = np.array(x_vals)
        y_arr = np.array(y_vals)

        # 同じ回のデータなら長さは必ず一致する
        if len(x_arr) == len(y_arr):
          mask = (y_arr > 0) & (x_arr > 0)
          X_flat.extend(x_arr[mask])
          Y_flat.extend(y_arr[mask])

      if len(X_flat) > 0:
        x_min, x_max = min(X_flat), max(X_flat)
        y_min, y_max = min(Y_flat), max(Y_flat)

        xbins = np.logspace(np.log10(x_min), np.log10(x_max))
        ybins = np.logspace(np.log10(y_min), np.log10(y_max))

        h = plt.hist2d(X_flat, Y_flat, bins=[xbins, ybins], cmap='inferno', norm=LogNorm())

        plt.colorbar(h[3], label='Frequency of Simulated Data points')
      else:
        print("Warning: No valid spectral data for heatmap.")

      plt.xscale('log')
      plt.yscale('log')
      plt.xlabel('Energy (keV)')
      plt.ylabel('Counts s$^{-1}$ keV$^{-1}$')
      plt.title(fr'Simulated Spectra Distribution:{file_name} ($N={success_count}$)')
      plt.grid(True, which="both", ls="--", alpha=0.3)
      plt.xlim(4, 8) # 必要に応じて範囲指定

      spec_plot_path = os.path.join(mc_output_dir, f"{file_name}_mc_spectra_density_{n_sim}.png")
      plt.savefig(spec_plot_path)
      plt.close()
      print(f"  Saved Spectral Density Plot: {spec_plot_path}")


    #生データをCSVに保存
    mc_csv_path = os.path.join(mc_output_dir, f"{file_name}_mc_{n_sim}.csv")
    np.savetxt(mc_csv_path, np.column_stack([sim_delta_chi2_array, sim_f_array]), delimiter=",", header="Simulated_Delta_Chi2,Simulated_F_Values", comments="")
    print(f"  Saved MC Data: {mc_csv_path}")

    # 2. ヒストグラムの作成と保存
    fig_hist, (ax1_hist, ax2_hist) = plt.subplots(2, 1, figsize=(10, 6), constrained_layout=True)

    # ヒストグラムの描画
    # Delta Chi2用のビン
    max_d_chi2 = np.max(sim_delta_chi2_array)
    bins_d_chi2 = np.arange(0, max_d_chi2 + 1.0, 1)

    # F値用のビン
    max_f = np.max(sim_f_array)
    bins_f = np.arange(0, max_f + 1.0, 0.1)

    ax1_hist.hist(sim_delta_chi2_array, bins=bins_d_chi2, color='skyblue', edgecolor='black', alpha=0.7, label='Simulated Null Distribution')
    ax1_hist.axvline(real_delta_chi2, color='red', linestyle='dashed', linewidth=2, label=rf'Observed $\Delta\chi^2$ ({real_delta_chi2:.2f})')

    ax2_hist.hist(sim_f_array, bins=bins_f, color='skyblue', edgecolor='black', alpha=0.7, label='Simulated Null Distribution')
    ax2_hist.axvline(real_f_val, color='red', linestyle='dashed', linewidth=2, label=rf'Observed $F$ ({real_f_val:.2f})')

    fig_hist.suptitle(f'Monte Carlo Simulation:{file_name} (N={success_count})\n$p_{{mc}} = {p_val_mc:.4f}$')

    ax1_hist.set_xlabel(r'$\Delta \chi^2$ (Base - Comp)')
    ax1_hist.set_ylabel('Frequency')
    ax1_hist.set_yscale('log')
    ax1_hist.legend()
    ax1_hist.set_xlim(0, None)
    ax1_hist.grid(True, alpha=0.3)

    ax2_hist.set_xlabel(r'$F$')
    ax2_hist.set_ylabel('Frequency')
    ax2_hist.set_yscale('log')
    ax2_hist.legend()
    ax2_hist.set_xlim(0, None)
    ax2_hist.grid(True, alpha=0.3)

    mc_plot_path = os.path.join(mc_output_dir, f"{file_name}_mc_hist_{n_sim}.png")
    fig_hist.savefig(mc_plot_path)

    print(f"  Saved MC Plot: {mc_plot_path}")

    return p_val_mc, threshold_95, sim_delta_chi2_array

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
    if sim_delta_chi2_array is None:
      mc_output_dir = os.path.join(OUTPUT_DIR, "mc_results")
      list_candidate_file  = sorted(glob.glob(os.path.join(mc_output_dir, "seglist_*_mc_*.csv"))) # ※ファイル名のパターンは環境に合わせて調整してください

      # もし seglist_ がファイル名に含まれていない場合は以下のように修正
      if not list_candidate_file:
        list_candidate_file = sorted(glob.glob(os.path.join(mc_output_dir, f"{file_name}_mc_*.csv")))

      if list_candidate_file:
        latest_file = max(
          list_candidate_file,
          key=lambda f: int(re.search(r'mc_([0-9]+)', os.path.basename(f)).group(1)) if re.search(r'mc_([0-9]+)', os.path.basename(f)) else 0
        )
        print(f"Using Null MC Result: {os.path.basename(latest_file)}")
        mc_data = pd.read_csv(latest_file)

        null_delta_chi2 = np.array(mc_data['Simulated_Delta_Chi2'])
        threshold_chi2 = np.percentile(null_delta_chi2, 99.73)
        print(f"Detection Threshold (99.73%): Delta Chi2 > {threshold_chi2:.2f}")
      else:
        print("Warning: No MC result file found. Using theoretical threshold approx 4.61 (90%) or 9.21 (99%).")
        threshold_chi2 = 9.21 # Default fallback
    else:
      null_delta_chi2 = sim_delta_chi2_array
      threshold_chi2 = np.percentile(null_delta_chi2, 99.73)
      print(f"Detection Threshold (99.73%): Delta Chi2 > {threshold_chi2:.2f}")

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

    # Normごとのループはシリアルのまま（早期終了判定のため）
    print(f"Base Params: {best_continuum_params}")
    for test_norm in target_norm_list:

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
      pass_count = 0
      with concurrent.futures.ProcessPoolExecutor(max_workers=use_workers) as executor:
        # tqdmで進捗表示
        results = list(tqdm(executor.map(limit_worker, worker_args), total=n_sim, desc=f"Norm={test_norm:.1e}", leave=False))

      # 結果集計 (Trueの数をカウント)
      pass_count = sum(results)

      detection_prob = pass_count / n_sim
      results_norm.append(test_norm)
      results_prob.append(detection_prob)

      print(f"  Norm: {test_norm:.2e} -> Prob: {detection_prob*100:.1f}%")

      # 100%検出が続いたらループを抜ける（時短）
      if len(results_prob) > 3 and all(p >= 0.99 for p in results_prob[-3:]):
        print("  Reached 100% detection. Stopping loop.")
        break
    # --- Step 3: 結果の保存とプロット ---

    # CSV保存
    limit_dir = os.path.join(OUTPUT_DIR, "limit_results")
    os.makedirs(limit_dir, exist_ok=True)

    df_res = pd.DataFrame({"Norm": results_norm, "Probability": results_prob})
    csv_save_path = os.path.join(limit_dir, f"{file_name}_sensitivity.csv")
    df_res.to_csv(csv_save_path, index=False)
    print(f"\nSaved Sensitivity Data: {csv_save_path}")

    # プロット作成
    plt.figure(figsize=(8, 6))
    plt.plot(results_norm, results_prob, 'o-', color='navy', label='Detection Probability')

    plt.xscale('log')
    plt.xlabel('Injected Fe Line Norm')
    plt.ylabel('Detection Probability')
    plt.ylim(-0.1, 1.1)
    plt.title(f'Sensitivity Curve: {file_name}\n(Threshold $\Delta\chi^2$ > {threshold_chi2:.2f})')
    plt.grid(True, which="both", ls="--", alpha=0.3)
    plt.legend()

    plot_save_path = os.path.join(limit_dir, f"{file_name}_sensitivity_curve.png")
    plt.savefig(plot_save_path)
    plt.close()
    print(f"Saved Sensitivity Plot: {plot_save_path}")

    return results_norm, results_prob

  def generate_custom_norms():
    # 基準となる数字
    bases = [1, 5]
    # 10のマイナス6乗から10の3乗（1000）まで
    exponents = range(-6, 6)

    norm_list = []
    for e in exponents:
      for b in bases:
        val = b * (10 ** e)
        if val <= 1000:
          norm_list.append(val)

    # 重複を削除してソート（念のため）
    return sorted(list(set(norm_list)))

  #グラフエリアの作成
  fig_spec, (ax1_spec, ax2_spec) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [2, 1]}, constrained_layout=True)
  plt.subplots_adjust(hspace=0.0)

  #BackGroundの種類ごとに処理
  for bkgtype in ["3c50", "scorpion"]:
    if bkgtype=="scorpion":
      if tf_scorpion:
        pass
      else:
        continue
    #load_dataでロードしたデータをtreat_dataに与えて各種データを取得
    s = load_data(file_name, bkgtype)
    if s is None:
      continue
    x_vals, x_err, y_net, y_err, y_bkg, y_tot = treat_data(s)

    #データのプロット
    ax1_spec.errorbar(x_vals, y_tot, fmt='.', label=f'Total({bkgtype})', alpha=0.3)
    ax1_spec.errorbar(x_vals, y_net, xerr=x_err, yerr=y_err, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
    #ax1_spec.errorbar(x_vals, y_net, yerr=y_err, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
    ax1_spec.step(x_vals, y_bkg, where='mid', label=f'Background({bkgtype})', alpha=0.3)

    ftest_results = {}

    colors = ["C3", "C4", "C5", "C6", "C7", "C8", "C9"]

    for i, (name, config) in enumerate(MODELS.items()):
      if only_model == None:
        pass
      else:
        if name not in only_model:
          continue

      #fitを実行
      s = load_data(file_name, bkgtype)
      m, chi2, dof, red_chi2, m_vals = run_fit(config)

      print(f"[{name}] Red.Chi2: {red_chi2:.2f}")

      if max(m_vals) > 0:
        ax1_spec.step(x_vals, m_vals, where='mid', label=f'{name}({bkgtype})($\chi^2_\\nu$={red_chi2:.2f})', linewidth=2, color=colors[i])

      residuals = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y_net, m_vals, y_err)]
      ax2_spec.errorbar(x_vals, residuals, xerr=x_err, yerr=1, fmt='.', alpha=0.6, label=f"Residuals({bkgtype})({name})", color=colors[i])


      csv_path = os.path.join(OUTPUT_DIR, f'{file_name}_{bkgtype}_{name}.csv')

      row_data = zip(x_vals, x_err, y_tot, y_net, y_err, m_vals, residuals)

      with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        header = [
          'Energy_keV',       # x_vals
          'Energy_Error_keV', # x_err (ビン幅の半分)
          'Total_Counts',     # y_tot
          'Net_Counts',       # y_net
          'Net_Error',        # y_err
          'Model_Values',     # m_vals
          'Residuals_Sigma'   # residuals ((data-model)/error)
        ]
        writer.writerow(header)
        writer.writerows(row_data)

      print(f"  Saved CSV: {csv_path}")

      summary_dir = cfg["spectrum"]["path"]["summary"]
      summary_csv_path = os.path.join(summary_dir, 'summary.csv')

      run_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

      try:
        exposure = xspec.AllData(1).exposure
      except:
        exposure = 0

      def error_pm(val, err_low, err_high):
        if err_low != 0 and err_high != 0:
          err_minus = val - err_low
          err_plus = err_high - val
        else:
          err_minus = 0
          err_plus = 0
        return err_minus, err_plus

      #ztbabs
      target_param_idx = 2

      param = m(target_param_idx)
      param02_val = param.values[0]

      param02_err = error_pm(param02_val, param.error[0], param.error[1])

      param02_err_minus = param02_err[0]
      param02_err_plus = param02_err[1]

      #Photon Index
      target_param_idx = 4

      param = m(target_param_idx)
      param04_val = param.values[0]

      param04_err = error_pm(param04_val, param.error[0], param.error[1])

      param04_err_minus = param04_err[0]
      param04_err_plus = param04_err[1]

      stat_val = xspec.Fit.statistic
      dof_val = xspec.Fit.dof

      try:
        nhp = scipy.stats.chi2.sf(stat_val, dof_val)
      except:
        nhp = 0.0

      file_exists = os.path.isfile(summary_csv_path)

      with open(summary_csv_path, 'a', newline='') as f:
        writer = csv.writer(f)

        # ファイルが新規作成のときだけヘッダーを書く
        if not file_exists:
          header = [
            'Exec_Date',       # 実行日時
            'Group_Name',      # groupの名前
            'Model',           # Model名
            'Exposure_s',      # Exposure
            'zTBabs_nH_val',
            'zTBabs_nH_err_minus',
            'zTBabs_nH_err_plus',
            'Photon_Index',    # Photon Index
            'Photon_Index_err_minus',     # -
            'Photon_Index_err_plus',      # +
            'Fit_Stat_Chi2',   # Fit Stat.
            'DOF',             # d.o.f.
            'Nhp'              # Nhp
          ]
          writer.writerow(header)

        # データ行
        writer.writerow([
          run_time,
          file_name,
          name,
          exposure,
          f"{param02_val:.5f}",
          f"{param02_err_minus:.5f}",
          f"{param02_err_plus:.5f}",
          f"{param04_val:.5f}",
          f"{param04_err_minus:.5f}",
          f"{param04_err_plus:.5f}",
          f"{stat_val:.2f}",
          dof_val,
          f"{nhp:.3e}"
        ])

      print(f"  Saved Summary: {summary_csv_path}")

      ftest_results[name] = {"chi2": chi2, "dof": dof}

    #ftest_resultsに貯めたデータを用いてftest
    ftest_csv_path = os.path.join(summary_dir, 'ftest.csv')
    file_exists = os.path.isfile(ftest_csv_path)

    with open(ftest_csv_path, 'a', newline='') as f:
      writer = csv.writer(f)

      # ファイルが新規作成のときだけヘッダーを書く
      if not file_exists:
        header = ['Exec_Date',
                  'File',
                  'base_name',
                  'comp_name',
                  'Chi2_base',
                  'DOF_base',
                  'Chi2_comp',
                  'DOF_comp',
                  'Delta_Chi2',
                  'f_val',
                  'p_val_ftest',
                  'p_val_mc'
        ]
        writer.writerow(header)

    for i, (name, config) in enumerate(MODELS.items()):
      if i == 0:
        base_name = name
        chi2_base = ftest_results[base_name]["chi2"]
        dof_base  = ftest_results[base_name]["dof"]

      else:
        comp_name = name
        chi2_comp  = ftest_results[comp_name]["chi2"]
        dof_comp   = ftest_results[comp_name]["dof"]

        print("\n=== F-Test Results (Bevington Method) ===")

        delta_chi2 = chi2_base - chi2_comp
        delta_dof  = dof_base - dof_comp

        if delta_dof <= 0:
          print("Warning: DOF did not decrease. Check if parameters were correctly freed.")
          f_value = 0
          p_value = 1.0
        elif delta_chi2 < 0:
          print("Warning: Chi2 increased with added parameter. Fit might have failed.")
          f_value = 0
          p_value = 1.0
        else:
          # Bevington p.204 F_chi formula
          # 分子: カイ二乗の改善量 / 自由度の差
          numerator = delta_chi2 / delta_dof
          # 分母: 新しいモデルの換算カイ二乗 (Chi2 / DOF)
          denominator = chi2_comp / dof_comp

          f_value = numerator / denominator
          p_value = xspec.Fit.ftest(chi2_comp, dof_comp, chi2_base, dof_base)

          # 3. 結果の表示と保存
          print(f"Model 1: {base_name}(Chi2={chi2_base:.2f}, DOF={dof_base})")
          print(f"Model 2: {comp_name}(Chi2={chi2_comp:.2f}, DOF={dof_comp})")
          print(f"{'-'*30}")
          print(f"Delta Chi2 : {delta_chi2:.2f}")
          print(f"Delta DOF  : {delta_dof}")
          print(f"F-statistic: {f_value:.4f}")
          print(f"Probability: {p_value:.3e}")
          print(f"{'-'*30}")

          p_value_mc = -1.0
          sim_delta_chi2_array = None
          if is_mc:
            p_value_mc, _, sim_delta_chi2_array = run_monte_carlo(MODELS[base_name], MODELS[comp_name], delta_chi2, f_value, delta_dof, n_mc, s
            )
            if p_value_mc is not None:
              print(f"Prob(MC)  : {p_value_mc:.3e}")
            else:
              print("Prob(MC)  : Failed")
              p_value_mc = -1.0

          if is_limit:
            target_norm_list = generate_custom_norms()
            check_detection_limit(
              cfg,
              target_norm_list,
              MODELS[base_name],
              MODELS[comp_name],
              s,
              n_sim=n_limit,
              sim_delta_chi2_array=sim_delta_chi2_array
            )

          print(f"{'-'*30}")

          with open(ftest_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
              run_time,
              file_name,
              base_name,
              comp_name,
              f"{chi2_base:.2f}",
              dof_base,
              f"{chi2_comp:.2f}",
              dof_comp,
              f"{delta_chi2:.2f}",
              f"{f_value:.2f}",
              f"{p_value:.4f}",
              f"{p_value_mc:.4f}"
            ])

  #plotの整理
  fig_spec.suptitle(f'Spectrum:{file_name}')

  ax1_spec.axvline(5.560, linestyle='--', color="black", alpha=0.2, label="Fe(E=5.560 keV)")
  ax2_spec.axvline(5.560, linestyle='--', color="black", alpha=0.2, label="Fe(E=5.560 keV)")


  ax1_spec.set_xscale('log')
  ax1_spec.set_yscale('log')
  ax1_spec.set_xlim(1, 10)

  if tf_eeufspec:
    ax1_spec.set_ylabel(r'Energy Flux ($E^2 F_E$) [$\mathrm{erg \cdot cm^2\cdot s^{-1}}$]')
  elif not tf_eeufspec:
    ax1_spec.set_ylabel(r'Counts s$^{-1}$ keV$^{-1}$')

  ax1_spec.legend(framealpha=0.1, bbox_to_anchor=(1.05, 1), loc='upper left')
  ax1_spec.grid(True, which="both", ls="--", alpha=0.3)

  ax2_spec.axhline(0,color="black", linestyle='--', alpha=0.5)
  ax2_spec.set_xscale('log')
  ax2_spec.set_ylabel('(Data-Model)/Error')
  ax2_spec.set_xlabel('Energy (keV)')
  ax2_spec.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
  ax2_spec.legend(framealpha=0.1, bbox_to_anchor=(1.05, 1), loc='upper left')
  ax2_spec.grid(True, which="both", ls=":", alpha=0.5)

  option_figure_name=[]

  if tf_eeufspec:
    option_figure_name.append("_eeufspec")
  elif not tf_eeufspec:
    option_figure_name.append("_plot")

  if tf_scorpion:
    option_figure_name.append("_withScorpion")
  elif not tf_scorpion:
    option_figure_name.append("_noScorpion")

  figure_name = str(file_name)
  for option in option_figure_name:
    figure_name += option

  figure_path = os.path.join(OUTPUT_DIR, figure_name)

  fig_spec.savefig(figure_path)
  print(f"\nグラフを '{figure_path}' に保存しました。")

if __name__ == "__main__":
  run_spectrum_analysis(default_cfg)