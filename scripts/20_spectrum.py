import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

xspec.AllData.clear()
xspec.AllModels.clear()

xspec.Fit.statMethod = "chi"

# --- パスの設定 (ご自身の環境に合わせて書き換えてください) ---
ObsID = "5420250101"
obs_directory = os.path.join("/home/heasoft/data", ObsID)
data_filename = f"ni{ObsID}_src.pha"
arf_filename = f"ni{ObsID}.arf"
rmf_filename = f"ni{ObsID}.rmf"
bkg01_filename = f"ni{ObsID}_bkg_3c50.pi"
bkg02_filename = f"ni{ObsID}_bkg_scorp.pha"

data_file = os.path.join(obs_directory, data_filename)
arf_file = os.path.join(obs_directory, arf_filename)
rmf_file = os.path.join(obs_directory, rmf_filename)
bkg01_file = os.path.join(obs_directory, bkg01_filename)
bkg02_file = os.path.join(obs_directory, bkg02_filename)

try:
  # スペクトルを読み込む
  load_command = f"1:1 {data_file} 2:2 {data_file}"
  xspec.AllData(load_command)
  
  # ハンドルを取得
  s01 = xspec.AllData(1) # Spectrum 1
  s02 = xspec.AllData(2) # Spectrum 2
  
  # 統計誤差の設定
  xspec.AllModels.systematic = 0.01
  
  # バックグラウンドを読み込む
  s01.background = bkg01_file
  s02.background = bkg02_file
  
  # レスポンスファイル(rmf/arf)を設定
  s01.response = rmf_file
  s01.response.arf = arf_file
  s02.response = rmf_file
  s02.response.arf = arf_file
  
  print(f"Loaded S1 (Group {s01.dataGroup}) BKG: {s01.background.fileName}")
  print(f"Loaded S2 (Group {s02.dataGroup}) BKG: {s02.background.fileName}")
  
  # 解析するエネルギー範囲を指定 (例: 0.5keV - 10.0keV)
  s01.ignore("**-0.3 10.0-**")
  s02.ignore("**-0.3 10.0-**")
  
except Exception as e:
  print(f"データ読み込みエラー: {e}")

# --- モデル定義 (powerlaw) ---
print("\n--- 2. Defining Model (powerlaw) ---")
m = xspec.Model("phabs * powerlaw")

# === パラメータ設定 ===
m(1).values = 1.0
m(2).values = 1.5
m(3).values = 1.0

#m(4).link = ""
#m(4).values = 1.0
#m(5).link = ""
#m(5).values = 1.5
#m(6).link = ""
#m(6).values = 1.0

# モデル確認
m.show()

# --- フィッティング ---
print("\n--- 3. Fitting ---")
xspec.Fit.query = "yes"
xspec.Fit.perform()

# 結果表示
chi2 = xspec.Fit.statistic
dof = xspec.Fit.dof
red_chi2 = chi2 / dof if dof > 0 else 0

print(f"\nReduced Chi-Squared: {red_chi2:.2f}")

# --- エラー計算 ---
try:
    print("\nCalculating errors for ALL parameters (1-6)...")
    # Group 1 (1-3) と Group 2 (4-6) 両方のエラーを計算
    xspec.Fit.error("1 2 3 4 5 6")
except Exception as e:
    print(f"Error calc skipped: {e}")

# --- 値の比較表示 ---
print("\n=== Comparison (3C50 vs SCORPEON) ===")
print(f"{'Param':<8} | {'3C50 (Spec1)':<20} | {'SCORPEON (Spec2)':<20}")
print("-" * 55)

# 値とエラーを取り出して表示する関数
def get_val_err(idx):
    val = m(idx).values[0]
    # error計算が走っていない場合は (0,0) になる
    err_l = m(idx).error[0]
    err_h = m(idx).error[1]
    return f"{val:.4f} ({err_l:.3f}-{err_h:.3f})"

print(f"nH       | {get_val_err(1):<20} | {get_val_err(1):<20}")
print(f"Gamma    | {get_val_err(2):<20} | {get_val_err(2):<20}")
print(f"Norm     | {get_val_err(3):<20} | {get_val_err(3):<20}")
print("-" * 55)

# XSPECからプロット用データを取得
xspec.Plot.xAxis = "keV"
xspec.Plot("data") # data, model, residualsなどを準備

# データの取得
x1_vals = xspec.Plot.x(1)
x1_err = xspec.Plot.xErr(1)
y1_net = xspec.Plot.y(1)
y1_err = xspec.Plot.yErr(1)
m1_vals = xspec.Plot.model(1)
x2_vals = xspec.Plot.x(2)
x2_err = xspec.Plot.xErr(2)
y2_net = xspec.Plot.y(2)
y2_err = xspec.Plot.yErr(2)
m2_vals = xspec.Plot.model(2)

xspec.Plot('Background')
y1_bkg  = xspec.Plot.y(1)
y2_bkg  = xspec.Plot.y(2)

y_tot = [n + b for n, b in zip(y1_net, y1_bkg)]

# Matplotlibで描画
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

# 1. 観測データ (対数軸の方が見やすい場合が多いです)
ax1.errorbar(x1_vals, y_tot, fmt='.', label='Total', alpha=0.3)
ax1.errorbar(x1_vals, y1_net, yerr=y1_err, fmt='.', label='Net(3C50)', alpha=0.3)
ax1.step(x1_vals, y1_bkg, where='mid', label='Background(3C50)', alpha=0.3)
ax1.errorbar(x2_vals, y2_net, yerr=y2_err, fmt='.', label='Net(scorpion)', alpha=0.3)
ax1.step(x2_vals, y2_bkg, where='mid', label='Background(scorpion)', alpha=0.3)

# 2. モデル
#ax1.plot(x1_vals, m1_vals, label='Best-fit Model(3c50)', color='red', linewidth=2)
#ax1.plot(x2_vals, m2_vals, label='Best-fit Model(scorpion)', color='red', linewidth=2)

# グラフの装飾
ax1.set_xscale('log')
ax1.set_yscale('log')
ax1.set_xlabel('Energy (keV)', fontsize=14)
ax1.set_ylabel('Counts s$^{-1}$ keV$^{-1}$', fontsize=14)
ax1.set_title(f'NICER Spectrum Fit (Reduced Chi2: {xspec.Fit.statistic / xspec.Fit.dof:.2f})')
ax1.legend()
ax1.grid(True, which="both", ls="--", alpha=0.3)

# --- 下段: 残差 (Residuals) ---
# (データ - モデル) / 誤差 = シグマ単位のズレ
residuals1 = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y1_net, m1_vals, y1_err)]
residuals2 = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y2_net, m2_vals, y2_err)]

ax2.errorbar(x1_vals, residuals1, yerr=1.0, fmt='.', alpha=0.6)
ax2.errorbar(x1_vals, residuals2, yerr=1.0, fmt='.', alpha=0.6)
ax2.axhline(0, color='red', linestyle='--') # ゼロライン
ax2.set_ylabel('(Data-Model)/Error', fontsize=10)
ax2.set_xlabel('Energy (keV)', fontsize=12)
ax2.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
ax2.set_xscale('log')
ax2.grid(True, which="both", ls=":", alpha=0.5)

# 保存
fig.savefig("results/spectrum_fit.png")
print("\nグラフを 'spectrum_fit.png' に保存しました。")