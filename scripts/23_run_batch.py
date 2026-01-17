import yaml
import subprocess
import os
import sys

# 設定ファイルのパス
CONFIG_PATH = "scripts/config.yaml"

def run_batch(start=0, end=70):
  # 元のconfigをバックアップ
  with open(CONFIG_PATH, 'r') as f:
    original_config_str = f.read()

  try:
    for i in range(start, end + 1):
      seg_num = f"{i:03d}"
      target_list = f"seglist_indiv{seg_num}.csv"
      target_name = f"seglist_indiv{seg_num}"

      print(f"\n{'='*40}")
      print(f"Processing: {target_name} ({i}/{end})")
      print(f"{'='*40}")

      # リストファイルが存在するか確認
      list_path = os.path.join("scripts/individual_csvs", target_list)
      if not os.path.exists(list_path):
        print(f"⚠️  Skipping {target_name}: List file not found at {list_path}")
        continue

      # config.yaml を一時的に書き換え
      # (PyYAMLを使ってロード＆ダンプするとコメントが消える可能性があるため、
      #  単純な置換か、都度辞書を渡す構造にするのが理想ですが、
      #  ここでは subprocess で既存スクリプトを呼ぶためファイルを書き換えます)

      # YAML読み込み
      with open(CONFIG_PATH, 'r') as f:
        config_data = yaml.safe_load(f)

      # パラメータ書き換え
      config_data['spectrum']['path']['merge_list'] = f"scripts/individual_csvs/{target_list}"
      config_data['spectrum']['path']['merge_name'] = target_name

      # YAML保存
      with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

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
      f.write(original_config_str)

if __name__ == "__main__":
  # 00から70まで実行
  run_batch(0, 71)
