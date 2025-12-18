from astropy.io import fits
import os
import csv
import sys
import pandas as pd

result_root_dir = os.path.join("results", "lightcurve", "segments")

obs_list_path: int = os.path.join(result_root_dir, "segInfo_fixed.csv")

df = pd.read_csv(obs_list_path)

result_time_dir = os.path.join(result_root_dir, "time_fixed")

os.makedirs(result_time_dir, exist_ok=True)

for _, (_, segID, _, START, STOP) in df.iterrows():
  result_time_path = os.path.join(result_time_dir, f"{segID}.txt")
  with open(result_time_path, "w", encoding='utf-8') as time:
    start_met = str(START)
    stop_met = str(STOP)
    output:str = ' '.join([start_met, stop_met])
    time.write(output)