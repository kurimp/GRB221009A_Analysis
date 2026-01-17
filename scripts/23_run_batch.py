import yaml
import subprocess
import os
import sys
from scripts.utils.read_config import cfg as default_cfg

# 設定ファイルのパス
CONFIG_PATH = "scripts/config.yaml"

def run_batch(start=0, end=1000, cfg=default_cfg):
  with open(CONFIG_PATH, 'r') as f:
    original_cfg = f.read()

  try:
    lists_dir = cfg['spectrum02']['path']['list_dir']
    target_basename = cfg['spectrum02']['path']['seglist_basename']
    target_dir = os.path.join(lists_dir, target_basename)
    for i in range(start, end + 1):
      seg_num = f"{i:03d}"
      target_name = f"{target_basename}-{seg_num}"
      target_list = f"{target_name}.csv"

      print(f"\n{'='*40}")
      print(f"Processing: {target_name} ({i}/{end})")
      print(f"{'='*40}")

      # リストファイルが存在するか確認
      list_path = os.path.join(target_dir, target_list)
      if not os.path.exists(list_path):
        print(f"⚠️  Skipping {target_name}: List file not found at {list_path}")
        continue

      # パラメータ書き換え
      cfg['spectrum']['path']['merge_list'] = list_path
      cfg['spectrum']['path']['merge_name'] = target_name

      # YAML保存
      with open(CONFIG_PATH, 'w') as f:
        yaml.dump(cfg._data, f, default_flow_style=False, sort_keys=False)

      # --- 20_merge-grp.py の実行 ---
      print(f"Running 20_merge-grp.py for {seg_num}...")
      res20 = subprocess.run([sys.executable, "scripts/20_merge-grp.py"], capture_output=False)
      if res20.returncode != 0:
        print(f"❌ Error in 20_merge-grp.py for {seg_num}. Skipping next step.")
        continue

      # --- 21_spectrum.py の実行 ---
      print(f"Running 21_spectrum.py for {seg_num}...")
      res21 = subprocess.run([sys.executable, "scripts/21_spectrum.py"], capture_output=False)
      if res21.returncode != 0:
        print(f"❌ Error in 21_spectrum.py for {seg_num}.")
      else:
        print(f"✅ Success: {target_name}")

  finally:
    # 処理終了後（またはエラー時）に元のconfigに戻す
    print("\nRestoring original config.yaml...")
    with open(CONFIG_PATH, 'w') as f:
      f.write(original_cfg)

if __name__ == "__main__":
  # 00から70まで実行
  run_batch(0, 100)
