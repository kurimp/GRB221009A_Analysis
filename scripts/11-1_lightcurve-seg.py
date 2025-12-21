import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.time import Time
import numpy as np
import astropy.units as u
import os
import csv
import sys
import glob
import pandas as pd
import argparse
from lmfit.models import PowerLawModel
from lmfit.models import Model

# --- 引数設定 ---
parser = argparse.ArgumentParser(
  description="Lightcurve processing script.",
  formatter_class=argparse.RawTextHelpFormatter
)

# 必須のディレクトリ引数
parser.add_argument("data_directory", type=str, help="The path to the directory containing the observational data files.")

# オプション：時間除外 (例: --time 2025-01-01...)
parser.add_argument("--since", type=str, default=None,
                    help="Optional timestamp to exclude data after this time.\nFormat: ISO 8601 (e.g., 2025-10-31T12:00:00.000)")

# オプション：除外SegIDリスト (例: --exclude 5410670113-000,5410670114-005,5410670115-001)
parser.add_argument("--exclude", type=str, default=None,
                    help="Optional comma-separated list of segIDs to exclude.\nExample: 5410670113-000,5410670114-005,5410670115-001")

args = parser.parse_args()

# --- 値の取得と処理 ---
dirname = args.data_directory

# 時間の処理
since_time = None
if args.since:
  try:
    since_time = Time(args.since, format='isot', scale="tt")
  except ValueError:
    print(f"❌ Error: Invalid time format '{args.since}'. Please use ISO 8601.")
    sys.exit(1)

# segIDリストの処理（カンマ区切りの文字列をリストに変換）
excluded_segIDs = []
if args.exclude:
  # "101, 102, 103" -> ['101', '102', '103']
  excluded_segIDs = [segID.strip() for segID in args.exclude.split(',')]

# --- 確認用出力 ---
print(f"Data Directory: {dirname}")
print(f"Exclusion Time: {since_time}")
print(f"Excluded segIDs: {excluded_segIDs}")

list_datafilename = sorted(glob.glob(os.path.join(dirname, "*.lc")))

list_time_elapsed_indiv = []
list_rate_indiv = []
list_error_indiv = []
list_segID_indiv = []

list_time_elapsed_segID = []
list_rate_segID = []
list_error_segID = []
list_segID_segID = []

fig, ax = plt.subplots(figsize=(10, 6))

df_info = pd.DataFrame(columns=['segID', 'DATE-OBS', 'DATE-END', 'EXPOSURE'])

for datafilename in list_datafilename:
  datapath = datafilename
  with fits.open(datapath) as datafile:
    print("-"*15)
    #各データの情報を出力するか
    display_info = True
    
    #各種情報の整理と出力
    header_primary = datafile['PRIMARY'].header
    header_rate = datafile['RATE'].header
    
    #データの時刻系の取得
    time_system = header_rate.get('TIMESYS', 'TT').lower()
    
    #NICERミッション基準時刻の取得
    mjd_ref = header_rate['MJDREFI'] + header_rate['MJDREFF']
    t_ref_absolute = Time(mjd_ref, format='mjd', scale=time_system.lower())
    
    data = datafile['RATE'].data
    time = data['TIME']
    rate = data['RATE']
    error = data['ERROR']
    
    time_zero_val = header_rate.get('TIMEZERO', '0.0')
    t_start_val = header_rate.get('TSTART', '0.0')
    
    #base_met:そのsegIDの観測開始時点のMET
    if abs(time_zero_val) > 1e8:
      base_met = time_zero_val
    elif time[0] > 1e8:
      base_met = time_zero_val
    else:
      base_met = t_start_val + time_zero_val
    
    #それぞれを時"間"に変換
    base_met_delta = u.Quantity(base_met, u.s)
    time_col_delta = u.Quantity(time, u.s)
    
    #SegID開始時刻=NICER基準時刻+SegID開始までの時間
    t_seg_start = t_ref_absolute + base_met_delta
    
    #データ点の絶対時刻=SegID開始時刻+観測開始からデータ点までの時間
    time_abs = t_seg_start + time_col_delta
    
    segID = os.path.basename(datapath).split("_src_")[0].replace("ni", "")
    print(f"segID:{segID}")
    print(f"観測開始時刻:{t_seg_start.isot}")
    
    #除外時刻の判定
    if since_time is not None and t_seg_start >= since_time:
      print("The Observation Time is after the specified 'since' time.")
      continue
    
    #除外segIDの判定
    if str(segID) in excluded_segIDs:
      print(f"The segID({segID}) is specified for exclusion.")
      continue
    
    if display_info:
      print(f"MJDREF:{mjd_ref}")
      print(f"OBJECT:{header_primary.get('OBJECT', 'N/A')}")
      print(f"DATE-OBS:{header_primary.get('DATE-OBS', 'N/A')}")
      print(f"DATE-END:{header_primary.get('DATE-END', 'N/A')}")
      print(f"EXPOSURE:{header_rate.get('EXPOSURE', '0.0')}")
      print(f"TIMESYS:{time_system}")
      print(f"TIMEZERO:{header_rate.get('TIMEZERO', '0.0')}")
    
    if data is None or len(data) == 0:
      print(f"⚠️ Warning: No data found in {datafilename} (segID: {segID}). Skipping...")
      continue
    
    #if header_rate.get('EXPOSURE', '0.0') < 500:
    #  print(f"Skipping...")
    #  continue
    
    #各segIDの観測開始時刻、観測終了時刻の表の作成
    _df_info = pd.DataFrame({'segID':segID, 'DATE-OBS':header_primary.get('DATE-OBS', 'N/A'), 'DATE-END':header_primary.get('DATE-END', 'N/A'), 'EXPOSURE':header_rate.get('EXPOSURE', '0.0')}, index=[0])
    df_info = pd.concat([df_info, _df_info])
    
    #トリガーからの経過時間=データ点の絶対時刻-トリガー時刻
    trigger_MJD = 59861.55347211
    time_abs_from_trigger = (time_abs - Time(trigger_MJD, format='mjd', scale='utc')).to_value(u.s)
    
    #bin幅の取得
    bin_width = header_rate.get('TIMEDEL', 0.0)
    
    duration = ((time_abs_from_trigger[-1]+bin_width)-time_abs_from_trigger[0])
    count_average = rate.mean()
    count_sum = count_average * duration
    
    count_error = np.sqrt(np.sum(error**2)) / len(error)
    
    segID_list = [segID for _ in range(len(time_abs_from_trigger))]
    
    list_time_elapsed_indiv.extend(time_abs_from_trigger)
    list_rate_indiv.extend(rate)
    list_error_indiv.extend(error)
    list_segID_indiv.extend(segID_list)
    
    list_time_elapsed_segID.append(time_abs_from_trigger[0])
    list_rate_segID.append(count_average)
    list_error_segID.append(count_error)
    list_segID_segID.append(segID)

for _ in range(5):
  try:
    tf_ana = input("Enter 1 for analysis per segID, or 0 otherwise (default is 1).:")
    if tf_ana == "":
      tf_ana = True
    else:
      tf_ana = bool(int(tf_ana))
  except Exception:
    print("Please input '1' or '0'.")
  else:
    break
else:
  print("Processing interrupted.")

if tf_ana:
  title_disc = "segID"
  list_time_elapsed = list_time_elapsed_segID
  list_rate = list_rate_segID
  list_error = list_error_segID
  list_segID = list_segID_segID
elif not tf_ana:
  title_disc = "Indiv"
  list_time_elapsed = list_time_elapsed_indiv
  list_rate = list_rate_indiv
  list_error = list_error_indiv
  list_segID = list_segID_indiv

list_time_elapsed_second = [td for td in list_time_elapsed]
zip_datas = zip(list_segID, list_time_elapsed_second, list_rate, list_error)

for _ in range(5):
  try:
    tf = input("Enter 1 to perform fitting, or 0 otherwise (default is 0).:")
    if tf == "":
      tf = False
    else:
      tf = bool(int(tf))
  except Exception:
    print("Please input '1' or '0'.")
  else:
    break
else:
  print("Processing interrupted.")

zip_datas = sorted(zip_datas, key=lambda row: row[1])
list_datas = list(zip(*zip_datas))

segID_data = np.array(list_datas[0])
x_data = np.array(list_datas[1])
y_data = np.array(list_datas[2])
error_data = np.array(list_datas[3])

ax.errorbar(x_data, y_data, error_data, fmt='x', capsize=0, label="data", alpha = 0.5)

def BrokenPowerLawModel(x, amplitude, t_break, alpha1, alpha2):
  """
  x: 時間
  amplitude: 振幅（正規化定数）
  t_break: 折れ曲がる時間
  alpha1: ブレイク前の傾き
  alpha2: ブレイク後の傾き
  """
  # x < t_break の部分と x >= t_break の部分で式を変える
  # ※計算を安定させるため、t_breakで正規化して繋げることが多いです
  
  x = np.array(x, dtype=float)
  
  if t_break <= 0:
    return np.ones_like(x) * 1e30
  
  model_output = np.zeros_like(x, dtype=float)
  
  # ブレイク前
  mask1 = x < t_break
  if np.any(mask1):
    model_output[mask1] = amplitude * (x[mask1] / t_break) ** (-alpha1)
  
  # ブレイク後
  mask2 = x >= t_break
  if np.any(mask2):
    model_output[mask2] = amplitude * (x[mask2] / t_break) ** (-alpha2)
  
  return model_output

if tf:
  valid_mask = (x_data > 0) & (error_data > 0) & np.isfinite(y_data)
  
  if np.sum(valid_mask) == 0:
    print("Error: No valid data points for fitting (all errors are 0 or x <= 0).")
    sys.exit(1)
  
  segID_safe = segID_data[valid_mask]
  x_safe = x_data[valid_mask]
  y_safe = y_data[valid_mask]
  error_safe = error_data[valid_mask]
  
  weights = 1.0 / error_safe
  
  for _ in range(5):
    try:
      tf_model = input("Enter 1 to use Broken Power Law Model, or 0 Power Law Model (default is 0).:")
      if tf_model == "":
        tf_model = False
      else:
        tf_model = bool(int(tf_model))
    except Exception:
      print("Please input '1' or '0'.")
    else:
      break
  else:
    print("Processing interrupted.")
  
  if tf_model:
    model_name = "Broken Power Law"
    model = Model(BrokenPowerLawModel)
    params = model.make_params()
    
    params['t_break'].set(value=(np.min(x_safe) + np.max(x_safe)) / 2, min=np.min(x_safe), max=np.max(x_safe))
    params['amplitude'].set(value=y_safe[0], min=0)
    params['alpha1'].set(value=1.0, min=-10, max=10)
    params['alpha2'].set(value=2.0, min=-10, max=10)
  elif not tf_model:
    model_name = "Power Law"
    model = PowerLawModel()
    params = model.guess(y_safe, x=x_safe)
  
  result = model.fit(y_safe, params, x=x_safe, weights=weights)
  print(result.fit_report())

  #result.fit(ax=ax)
  ax.plot(x_safe, result.best_fit, 'r-', label=f'Fitted {model_name} Curve')

#the Fermi-GBM trigger time (t0; 2022 October 9 at 13:16:59.99 UTC)
ax.set_title(f"GRB221009A's Light Curve({os.path.basename(dirname)})")
ax.set_xlabel('Elapsed Time from the Fermi-GBM trigger(2022 October 9 at 13:16:59.99 UTC) (seconds)')
ax.set_ylabel('Rate (counts/s)')
ax.set_xscale('log')
ax.set_yscale('log')
#ax.set_xlim(1, None)
ax.set_ylim(None, 10000)
#ax.set_xlim(datetime(2022, 10, 9, 0, 0, 0), datetime(2022, 10, 30, 0, 0, 0))

#ax.grid(True, which='both', linestyle=':', alpha=0.6)
ax.axhline(0.094, linestyle='--', color="black", alpha=0.5)
ax.minorticks_on()

#date_form = mdates.DateFormatter('%Y/%m/%d %H')
#ax.xaxis.set_major_formatter(date_form)
#fig.autofmt_xdate()

ax.legend()
plt.tight_layout()

#各種データの保存
data_path = str(dirname).split("collect/")[1]
data_name = data_path.replace("/", "_")
result_file_path = os.path.join("results", "lightcurve", data_path)
os.makedirs(result_file_path, exist_ok=True)

segInfo_path = os.path.join(result_file_path, "segInfo.csv")
result_data_path = os.path.join(result_file_path, "data.csv")
image_path = os.path.join(result_file_path, f"{title_disc}.png")

df_info.to_csv(segInfo_path)

with open(result_data_path, 'w', newline='', encoding='utf-8') as f:
  writer = csv.writer( f)
  writer.writerow(['segID', 'time', 'rate', 'error'])
  for (a, b, c, d) in zip_datas:
    writer.writerow((a, b, c, d))

plt.savefig(image_path, format="png", dpi=300)