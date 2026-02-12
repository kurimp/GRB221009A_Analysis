import yaml
import subprocess
import os
import sys
import csv
import pandas as pd
from scripts.utils.read_config import cfg as default_cfg

# ==========================================
# 設定エリア
# ==========================================

# 設定ファイルのパス
CONFIG_PATH = "scripts/config.yaml"

# 実行する解析プログラム
SensitivityPy = "21-2_limit.py"

# ==========================================
# バッチ処理メイン
# ==========================================
def run_batch(start=0, end=1000, cfg=default_cfg):
  with open(CONFIG_PATH, 'r') as f:
    original_cfg_str = f.read()

  try:
    lists_dir = cfg['spectrum02']['path']['list_dir']
    target_basename = cfg['spectrum02']['path']['seglist_basename']
    target_dir = os.path.join(lists_dir, target_basename)

    limit_name = cfg['spectrum02']['path']['limit_list']
    limit_path = os.path.join(lists_dir, limit_name)

    df_limit = pd.read_csv(limit_path)

    # ループ実行
    for i in range(start, end + 1):
      seg_num = f"{i:03d}"
      target_name = f"{target_basename}-{seg_num}"
      target_list = f"{target_name}.csv"

      print(f"\n{'='*60}")
      print(f"Processing: {target_name} ({i}/{end})")
      print(f"{'='*60}")

      # リストファイルの存在確認
      list_path = os.path.join(target_dir, target_list)
      if not os.path.exists(list_path):
        print(f"⚠️  Skipping {target_name}: List file not found at {list_path}")
        continue

      # -------------------------------------------------
      # config.yaml の書き換え
      # -------------------------------------------------

      row = df_limit[df_limit['name'] == target_name]

      if row.empty:
        print(f"⚠️  Skipping {target_name}: Not found in {limit_name}")
        continue

      # 値を取り出す (intに変換)
      norm_min = float(row['norm_min'].values[0])
      norm_max = float(row['norm_max'].values[0])

      cfg['spectrum']['path']['merge_list'] = list_path
      cfg['spectrum']['path']['merge_name'] = target_name

      current_norm_range = [norm_min, norm_max]
      cfg['spectrum']['parameters']['limit']['norm_range'] = current_norm_range

      print(f"Target Exponents: {current_norm_range}")
      # YAML保存 (これをサブプロセスが読み込む)
      with open(CONFIG_PATH, 'w') as f:
        yaml.dump(cfg._data, f, default_flow_style=False, sort_keys=False)

      # -------------------------------------------------
      # スクリプト実行
      # -------------------------------------------------

      print(f"Running {SensitivityPy} for {seg_num}...")
      res = subprocess.run([sys.executable, f"scripts/{SensitivityPy}"], capture_output=False)

      if res.returncode != 0:
        print(f"❌ Error in {SensitivityPy} for {seg_num}.")
      else:
        print(f"✅ Success: {target_name}")

  except KeyboardInterrupt:
    print("\n⚠️ Batch processing interrupted by user.")
  except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
  finally:
    # 処理終了後（またはエラー時）に元のconfigに戻す
    print("\nRestoring original config.yaml...")
    with open(CONFIG_PATH, 'w') as f:
      f.write(original_cfg_str)

if __name__ == "__main__":
    # ここで開始番号・終了番号を指定
    run_batch(0, 100)