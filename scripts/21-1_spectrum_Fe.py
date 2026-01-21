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

def run_spectrum_analysis(cfg):
  #===========config===========
  #plotのy軸表記選択。FluxならTrue。
  tf_eeufspec = False

  #使用するObsIDを選択。
  file_name = cfg['spectrum']['path']['merge_name']
  file_path = os.path.join(cfg['spectrum']['path']['merge_output'], file_name)

  #scorpionでのbackgroundを扱うかどうかを選択。使うならTrue。
  tf_scorpion = False

  #モンテカルロシミュレーションの実行の可否
  is_mc = cfg['spectrum']['parameters']['is_mc']
  n_mc = cfg['spectrum']['parameters']['mc_time']

  systematic = cfg['spectrum']['parameters']['systematic']
  ignoreRange = cfg['spectrum']['parameters']['ignoreRange']

  #特定のモデルのみ処理を実施したい場合、モデル名をlistで与える。なければNone。
  only_model = ["ZPL", "ZPL+Fe"]

  OUTPUT_DIR = f"results/spectrum/{file_name}"

  # 比較したいモデルのリスト
  # "モデル名": { "expr": "XSPECの式", "params": { パラメータ番号: "初期値設定文字列" } }
  MODELS = {
    "ZPL": {
      "expr": "tbabs * ztbabs * powerlaw",
      "params": {
        # 1: ztbabs (Galactic nH) -> 5.38e21 cm^-2 = 0.538
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
    elif bkgtype == "scorpion":
      bkg_filename = f"{file_name}_bkg_scorp.pha"
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
      xspec.Fit.error("2.706 1 2 3 4 5")
    except Exception as e:
      print(f"Error calculation failed: {e}")

    pho_index = m(4).values[0]
    pho_err_low = m(4).error[0]
    pho_err_high = m(4).error[1]
    print(f"Photon Index: {pho_index:.4f} (-{pho_index-pho_err_low:.4f}, +{pho_err_high-pho_index:.4f})")

    chi2 = xspec.Fit.statistic
    dof = xspec.Fit.dof
    red_chi2 = chi2 / dof if dof > 0 else 0

    xspec.Plot.xAxis = "keV"
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

    old_chatter = xspec.Xset.chatter
    old_logChatter = xspec.Xset.logChatter
    xspec.Xset.chatter = 0
    xspec.Xset.logChatter = 0

    current_dir = os.getcwd()
    temp_dir = os.path.join(OUTPUT_DIR, "mc_temp")
    os.makedirs(temp_dir, exist_ok=True)

    data_dir = os.path.abspath(file_path)
    os.chdir(temp_dir)

    sim_delta_chi2_list = []
    sim_f_list = []

    sim_spectra_y = []
    sim_spectra_x = []

    try:
      # RMFのパス解決
      rmf_name = spectrum_obj.response.rmf
      if os.path.isabs(rmf_name):
          rmf = rmf_name
      else:
          rmf = os.path.join(data_dir, rmf_name)

      # BKGのパス解決
      bkg_name = spectrum_obj.background.fileName
      if os.path.isabs(bkg_name):
        bkg = bkg_name
      else:
        bkg = os.path.join(data_dir, bkg_name)

      # ARFのパス解決（前回のエラー対応含む）
      arf = ""
      try:
        if spectrum_obj.response.arf:
            arf_name = spectrum_obj.response.arf
            if os.path.isabs(arf_name):
                arf = arf_name
            else:
                arf = os.path.join(data_dir, arf_name)
      except:
        arf = ""
      exposure = spectrum_obj.exposure
      print(f"{rmf=}")
      print(f"{arf=}")
      print(f"{bkg=}")
      print(f"{exposure=}")

      def make_local_link(abs_path):
        if not abs_path: return ""
        filename = os.path.basename(abs_path) # ファイル名だけ取り出す
        if not os.path.exists(filename):
          try:
            os.symlink(abs_path, filename) # Linux/Macならシンボリックリンク
          except:
            shutil.copy(abs_path, filename) # Windowsやリンク失敗時はコピー
        return filename # fakeitにはファイル名だけ渡す

      rmf = make_local_link(rmf)
      bkg = make_local_link(bkg)
      arf = make_local_link(arf)

    except Exception as e:
      print(f"MC Error: Could not get response info. {e}")
      xspec.Xset.chatter = old_chatter
      os.chdir(current_dir)
      return None

    xspec.AllData(1).notice("all")
    xspec.AllData(1).ignore(ignoreRange)

    m_base = setup_model(base_config)
    xspec.Fit.perform()

    best_params = []
    for i in range(1, m_base.nParameters + 1):
      best_params.append(m_base(i).values)

    fake_file_name = "fake_spec.pha"

    success_count = 0
    for i in range(n_sim):
      if (i + 1) % 10 == 0:
        sys.stdout.write(f"\rSimulation: {i+1}/{n_sim}")
        sys.stdout.flush()

      try:
        xspec.AllModels.clear()
        m_temp = setup_model(base_config)

        for idx, values in enumerate(best_params):
          m_temp(idx + 1).values = values

        fs = xspec.FakeitSettings(response=rmf, arf=arf, background=bkg, exposure=exposure, correction=1.0, fileName="temp_sim.fak")
        xspec.AllData.fakeit(1, fs, applyStats=True, filePrefix="")

        #baseでのfit
        m_base = setup_model(base_config)
        xspec.Fit.renorm()
        xspec.Fit.perform()
        chi2_base = xspec.Fit.statistic
        dof_base = xspec.Fit.dof

        xspec.Plot.xAxis = "keV"
        xspec.Plot("data")

        if len(sim_spectra_x) == 0:
          sim_spectra_x = xspec.Plot.x()

        sim_spectra_y.append(xspec.Plot.y())

        #compでのfit
        m_comp = setup_model(comp_config)
        xspec.Fit.renorm()
        xspec.Fit.perform()
        chi2_comp = xspec.Fit.statistic
        dof_comp = xspec.Fit.dof

        d_chi2 = chi2_base - chi2_comp
        d_dof = dof_base - dof_comp

        if d_dof > 0 and dof_comp > 0 and chi2_comp > 0:
          numerator = d_chi2 / d_dof
          denominator = chi2_comp / dof_comp
          f_val = numerator / denominator
        else:
          f_val = 0.0

        if d_chi2 > max(100, real_delta_chi2 * 2):
          print(f"\n[Warning] Huge Delta Chi2: {d_chi2:.1f}")

        sim_f_list.append(f_val)
        sim_delta_chi2_list.append(d_chi2)
        success_count += 1
      except Exception as e:
        print(f"MC Loop Error: {e}")
        continue

    xspec.Xset.chatter = old_chatter
    xspec.Xset.logChatter = old_logChatter

    os.chdir(current_dir)
    print("\nMC Finished.")

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

      x_base = np.array(sim_spectra_x)

      for y_vals in sim_spectra_y:
        y_arr = np.array(y_vals)

        mask = (y_arr > 0) & (x_base > 0)
        X_flat.extend(x_base[mask])
        Y_flat.extend(y_arr[mask])

      x_min, x_max = min(X_flat), max(X_flat)
      y_min, y_max = min(Y_flat), max(Y_flat)

      xbins = np.logspace(np.log10(x_min), np.log10(x_max), 100)
      ybins = np.logspace(np.log10(y_min), np.log10(y_max), 100)

      h = plt.hist2d(X_flat, Y_flat, bins=[xbins, ybins], cmap='inferno', norm=LogNorm())

      plt.colorbar(h[3], label='Frequency of Simulated Data points')

      try:
        xspec.Plot.xAxis = "keV"
        pass
      except:
        pass

      plt.xscale('log')
      plt.yscale('log')
      plt.xlabel('Energy (keV)')
      plt.ylabel('Counts s$^{-1}$ keV$^{-1}$')
      plt.title(f'Simulated Spectra Distribution (Null Hypothesis, N={success_count})')
      plt.grid(True, which="both", ls="--", alpha=0.3)
      plt.xlim(4, 8) # 必要に応じて範囲指定

      spec_plot_path = os.path.join(mc_output_dir, f"mc_spectra_density_{n_sim}.png")
      plt.savefig(spec_plot_path)
      plt.close()
      print(f"  Saved Spectral Density Plot: {spec_plot_path}")

    #生データをCSVに保存
    mc_csv_path = os.path.join(mc_output_dir, f"mc_{n_sim}.csv")
    np.savetxt(mc_csv_path, np.column_stack([sim_delta_chi2_array, sim_f_array]), delimiter=",", header="Simulated_Delta_Chi2,Simulated_F_Values", comments="")
    print(f"  Saved MC Data: {mc_csv_path}")

    # 2. ヒストグラムの作成と保存
    fig_hist, (ax1_hist, ax2_hist) = plt.subplots(2, 1, figsize=(10, 6))

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

    fig_hist.suptitle(f'Monte Carlo Simulation (N={success_count})\n$p_{{mc}} = {p_val_mc:.4f}$')

    ax1_hist.set_xlabel(r'$\Delta \chi^2$ (Base - Comp)')
    ax1_hist.set_ylabel('Frequency')
    ax1_hist.legend()
    ax1_hist.set_xlim(0, None)
    ax1_hist.grid(True, alpha=0.3)

    ax2_hist.set_xlabel(r'$F$')
    ax2_hist.set_ylabel('Frequency')
    ax2_hist.legend()
    ax2_hist.set_xlim(0, None)
    ax2_hist.grid(True, alpha=0.3)

    mc_plot_path = os.path.join(mc_output_dir, f"mc_hist_{n_sim}.png")
    fig_hist.savefig(mc_plot_path)

    print(f"  Saved MC Plot: {mc_plot_path}")

    return p_val_mc


  #グラフエリアの作成
  fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [2, 1]}, constrained_layout=True)
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
    ax1.errorbar(x_vals, y_tot, fmt='.', label=f'Total({bkgtype})', alpha=0.3)
    ax1.errorbar(x_vals, y_net, xerr=x_err, yerr=y_err, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
    #ax1.errorbar(x_vals, y_net, yerr=y_err, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
    ax1.step(x_vals, y_bkg, where='mid', label=f'Background({bkgtype})', alpha=0.3)

    ftest_results = {}

    colors = ["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
    #modelでのfitを実行
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
        ax1.plot(x_vals, m_vals, label=f'{name}({bkgtype})($\chi^2_\\nu$={red_chi2:.2f})', linewidth=2, color=colors[i])

      residuals = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y_net, m_vals, y_err)]
      ax2.errorbar(x_vals, residuals, xerr=x_err, yerr=1, fmt='.', alpha=0.6, label=f"Residuals({bkgtype})({name})", color=colors[i])

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

          # F分布の生存関数 (Survival Function = 1 - CDF) から確率を計算
          # これが「偶然にこれだけの改善が起きる確率」
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
          if is_mc:
            p_value_mc = run_monte_carlo(MODELS[base_name], MODELS[comp_name], delta_chi2, f_value, delta_dof, n_mc, s)
            if p_value_mc is not None:
              print(f"Prob(MC)  : {p_value_mc:.3e}")
            else:
              print("Prob(MC)  : Failed")
              p_value_mc = -1.0

            if os.path.exists("temp_sim.fak"):
              os.remove("temp_sim.fak")
            if os.path.exists("temp_sim_bkg.fak"):
              os.remove("temp_sim.fak")

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
  fig.suptitle(f'GRB221009A NICER Spectrum Fit:{file_name}')

  ax1.axvline(5.560, linestyle='--', color="black", alpha=0.2, label="Fe(E=5.560 keV)")
  ax2.axvline(5.560, linestyle='--', color="black", alpha=0.2, label="Fe(E=5.560 keV)")

  ax1.set_xscale('log')
  ax1.set_yscale('log')
  ax1.set_xlim(4, 8)

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
  ax2.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
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

  figure_name = str(file_name)
  for option in option_figure_name:
    figure_name += option

  figure_path = os.path.join(OUTPUT_DIR, figure_name)

  fig.savefig(figure_path)
  print(f"\nグラフを '{figure_path}' に保存しました。")

if __name__ == "__main__":
  run_spectrum_analysis(default_cfg)