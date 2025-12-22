import os
import pandas as pd
import shutil
from scripts.utils.read_config import cfg

result_root_dir = cfg['segment']['path']['result_root']
obs_list_path: int = os.path.join(result_root_dir, cfg['segment']['path']['obs_list_name'])
result_time_dir = os.path.join(result_root_dir, cfg['segment']['path']['result_time_dir'])

print(f"Reading list: {obs_list_path}")

# --- ファイルの読み込み ---
if not os.path.exists(obs_list_path):
  print(f"❌ Error: File not found at {obs_list_path}")
  exit(1)

df = pd.read_csv(obs_list_path)
total_rows = len(df)
print(f"📊 Found {total_rows} segments to process.")

if os.path.exists(result_time_dir):
  shutil.rmtree(result_time_dir)
if not os.path.exists(result_time_dir):
  os.makedirs(result_time_dir, exist_ok=True)
  print(f"📁 Created directory: {result_time_dir}")

print("⏳ Writing time files...")

for index, (_, segID, _, START, STOP) in df.iterrows():
  result_time_path = os.path.join(result_time_dir, f"{segID}.txt")
  with open(result_time_path, "w", encoding='utf-8') as time:
    start_met = str(START)
    stop_met = str(STOP)
    output:str = ' '.join([start_met, stop_met])
    time.write(output)
  current_num = index + 1
  print(f"Processed {current_num}/{total_rows}: {segID}.txt")