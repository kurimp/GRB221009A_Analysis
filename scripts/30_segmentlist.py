import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.time import Time
from astropy.table import Table
import numpy as np
import astropy.units as u
import os
import csv
import sys
import glob
import pandas as pd
import math
import argparse
from datetime import datetime
from lmfit.models import PowerLawModel
from lmfit.models import Model
import pprint

obs_list_path: int = os.path.join("scripts", "obs_list.txt")

try:
  with open(obs_list_path, 'r', encoding='utf-8') as f:
    _reader = csv.reader(f)
    _l = [row for row in _reader]
    obsIDs: list = [str(x) for x in list(zip(*_l))[0] if x[0] != "#"]
except FileNotFoundError:
  print(f"error:File""{obs_list_path}"" not found.")
  sys.exit(1)

result_root_dir = os.path.join("results", "lightcurve", "segments")
result_time_dir = os.path.join(result_root_dir, "time")
os.makedirs(result_time_dir, exist_ok=True)


result_info_dir:str = os.path.join(result_root_dir, f"segInfo.csv")
with open(result_info_dir, "w", encoding='utf-8') as info:
  writer_info = csv.writer(info)
  writer_info.writerow(['obsID', 'segID', 'TimeDataFile', 'START', 'STOP'])
  for obsID in obsIDs:
    obs_clevt_path: str = os.path.join("data", "obs", obsID, "xti", "event_cl", f"ni{obsID}_0mpu7_cl.evt")
    
    with fits.open(obs_clevt_path) as datafile:
      header_primary = datafile['PRIMARY'].header
      
      for i, row in enumerate(datafile['GTI'].data):
        segID:str = f"{obsID}-{i:03d}"
        result_time_path = os.path.join(result_time_dir, f"{segID}.txt")
        with open(result_time_path, "w", encoding='utf-8') as time:
          start_met = str(row['START'])
          stop_met = str(row['STOP'])
          output:str = ' '.join([start_met, stop_met])
          time.write(output)
        writer_info.writerow([obsID, segID, result_time_path, start_met, stop_met])