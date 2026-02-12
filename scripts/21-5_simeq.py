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
import io
from contextlib import redirect_stdout
import traceback

def get_simulated_eq(file_name, test_norm, data_row):

  file_path = os.path.join(cfg['spectrum']['path']['merge_output'], file_name)
  data_filename = f"{file_name}_grp.pha"
  bkg_filename = f"{file_name}_bkg_3c50.pha"

  grp_time = cfg['spectrum']['parameters']['grp_time']
  grp_time = 10
  ignoreRange = cfg['spectrum']['parameters']['ignoreRange']

  #MODELの定義
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

  def setup_model(model_config):
    xspec.AllModels.clear()
    m = xspec.Model(model_config['expr'])
    for idx, val_str in model_config['params'].items():
      m(idx).values = val_str
    return m

  #等価幅を計算する関数
  def output_eq():
    log_file = "xspec_temp_log_for_eq.txt"

    if os.path.exists(log_file):
      os.remove(log_file)

    xspec.Xset.openLog(log_file)
    xspec.Xset.logChatter = 10

    try:
      xspec.AllModels.eqwidth(4, err=False, number=10000, level=90, rangeFrac=0.2)
    finally:
      xspec.Xset.closeLog()

    with open(log_file, "r") as f:
      output = f.read()

    val_match = re.search(r"equiv width for Component \d+:\s+([\d\.eE+-]+)\s+keV", output)
    err_match = re.search(r"error range:\s+([\d\.eE+-]+)\s+-\s+([\d\.eE+-]+)\s+keV", output)

    if val_match is None:
      val_match = 0
    else:
      print(f"抽出された値: {val_match.group(1)}")
      val_match = val_match.group(1)
    if err_match is None:
      err_match = [0, 0]
    else:
      print(f"抽出された誤差範囲: {err_match.group(1)} to {err_match.group(2)}")
      err_match = [err_match.group(1), err_match.group(2)]

    print(f"{val_match=}", f"{err_match=}")

    os.remove(log_file)

    return val_match, err_match

  base_config = MODELS['ZPL']
  comp_config = MODELS['ZPL+Fe']

  current_dir = os.getcwd()

  eq_val = "0.0"
  eq_err = ["0.0", "0.0"]

  try:
    os.chdir(file_path)

    xspec.AllData.clear()

    s = xspec.Spectrum(data_filename)

    s.ignore(ignoreRange)

    m_base_real = setup_model(base_config)

    xspec.Fit.perform()

    best_continuum_params = []
    for i in range(1, m_base_real.nParameters + 1):
      best_continuum_params.append(m_base_real(i).values)

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

    eq_val, eq_err = output_eq()
    success = True

  except Exception as e:
    print(f"Error in {file_name}: {e}")
    # エラー時は保存せずにリターン
    return

  finally:
    os.chdir(current_dir)

  if success:
    #データの保存
    norm = test_norm
    prob = data_row.prob
    start = data_row.start
    end = data_row.end
    middle = data_row.middle
    width = data_row.width

    summary_dir = cfg["spectrum"]["path"]["summary"]
    result_csv_path = os.path.join(summary_dir, 'sim_eq.csv')

    file_exists = os.path.isfile(result_csv_path)

    with open(result_csv_path, 'a', newline='') as f:
      writer = csv.writer(f)
      if not file_exists:
        header = [
          'name',
          'norm',
          'prob',
          'start',
          'end',
          'middle',
          'width',
          'eq_val',
          'eq_err_minus',
          'eq_err_plus'
        ]

        writer.writerow(header)

      if eq_val is not None:
        eq_val = f"{float(eq_val):.5f}"
      if eq_err[0] is not None:
        eq_err[0] = f"{float(eq_err[0]):.5f}"
      if eq_err[1] is not None:
        eq_err[1] = f"{float(eq_err[1]):.5f}"

      # データ行
      writer.writerow([
        file_name,
        norm,
        prob,
        start,
        end,
        middle,
        width,
        eq_val,
        eq_err[0],
        eq_err[1]
      ])
    print(f"  Saved eq results: {result_csv_path}")

if __name__ == "__main__":
  lists_dir = cfg['spectrum02']['path']['list_dir']
  eq_list_name = cfg['spectrum02']['path']['limit_list']
  eq_list_name = "eq.csv"
  eq_path = os.path.join(lists_dir, eq_list_name)
  df_eq = pd.read_csv(eq_path)

  for row in df_eq.itertuples():
    get_simulated_eq(
      file_name=row.name,
      test_norm=row.norm,
      data_row=row
    )