import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

xspec.AllData.clear()
xspec.AllModels.clear()

xspec.Fit.statMethod = "chi"

# --- パスの設定 (ご自身の環境に合わせて書き換えてください) ---
# 例: マウントしたデータ内のphaファイル
# もしファイル名がわからなければ、terminalで ls data/ をして確認してください
obs_directory = "/home/heasoft/data/5420250101"
data_filename = "ni5420250101_src.pha"
arf_filename = "ni5420250101.arf"
rmf_filename = "ni5420250101.rmf"
bkg_filename = "ni5420250101_bkg.pi"

data_file = os.path.join(obs_directory, data_filename)
arf_file = os.path.join(obs_directory, arf_filename)
rmf_file = os.path.join(obs_directory, rmf_filename)
bkg_file = os.path.join(obs_directory, bkg_filename)


try:
  # スペクトルを読み込む
  s = xspec.Spectrum(data_file)
  
  # 統計誤差の設定
  xspec.AllModels.systematic = 0.01
  
  # バックグラウンドを読み込む
  s.background = bkg_file
  
  # レスポンスファイル(rmf/arf)を設定
  s.response = rmf_file
  s.response.arf = arf_file

  print(f"Loaded: {s.fileName}")

  # 解析するエネルギー範囲を指定 (例: 0.5keV - 10.0keV)
  s.ignore("**-0.3 10.0-**") 
  
except Exception as e:
    print(f"データ読み込みエラー: {e}")

# --- モデル定義 (powerlaw) ---
print("\n--- 2. Defining Model (powerlaw) ---")
m = xspec.Model("phabs * powerlaw")

# === パラメータ設定 ===
# 1: phabs.nH (吸収)
m.phabs.nH = 1.0          # 10^22 cm^-2

# 2: powerlaw.PhoIndex (ガンマ)
# 名前が 'pegpwrlw' ではなく 'powerlaw' になります
m.powerlaw.PhoIndex = 1.5 

# 3: powerlaw.norm (規格化)
# ★注意: これはフラックスではありません。「1keVでの光子数」です。
m.powerlaw.norm = 1.0     # 初期値

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

print("\n--- Fit Result ---")
print(f"Chi-Squared: {chi2:.2f}")
print(f"Reduced Chi-Squared: {red_chi2:.2f}")

# パラメータ取得
val_nh = m.phabs.nH.values[0]
val_gamma = m.powerlaw.PhoIndex.values[0]
val_flux = m.powerlaw.norm.values[0]

print(f"Best-fit nH: {val_nh:.4f}")
print(f"Best-fit Gamma: {val_gamma:.4f}")
print(f"Flux (0.5-10keV): {val_flux:.4f} (10^-12 erg/cm2/s)")

# エラーの計算
try:
  print("Calculating errors...")
  # パラメータ1(nH) と パラメータ2(Gamma) のエラーを計算
  # "1 2" はパラメータ番号
  xspec.Fit.error("1 2 3")
  
  # 結果の取得
  # error[0]=lower limit, error[1]=upper limit
  nh_err = m.phabs.nH.error 
  gamma_err = m.powerlaw.PhoIndex.error
  
  print(f"\nnH Error: {m.phabs.nH.error[0]:.4f} - {m.phabs.nH.error[1]:.4f}")
  print(f"Gamma Error: {m.powerlaw.PhoIndex.error[0]:.4f} - {m.powerlaw.PhoIndex.error[1]:.4f}")
  print(f"Flux Error: {m.powerlaw.norm.error[0]:.4f} - {m.powerlaw.norm.error[1]:.4f}")
except Exception as e:
  print(f"\nError calculation skipped (Chi-Sq too high): {e}")

# XSPECからプロット用データを取得
xspec.Plot.xAxis = "keV"
xspec.Plot("data") # data, model, residualsなどを準備

# データの取得
x_vals = xspec.Plot.x()
x_err = xspec.Plot.xErr()
y_net = xspec.Plot.y()
y_err = xspec.Plot.yErr()
m_vals = xspec.Plot.model()  # ベストフィットモデル

xspec.Plot('Background')
y_bkg  = xspec.Plot.y()

y_tot = [n + b for n, b in zip(y_net, y_bkg)]

# Matplotlibで描画
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

# 1. 観測データ (対数軸の方が見やすい場合が多いです)
ax1.errorbar(x_vals, y_net, yerr=y_err, fmt='.', label='Net', alpha=0.3)
#plt.step(x_vals, y_net, where='mid', label='Net', alpha=1)
ax1.step(x_vals, y_bkg, where='mid', label='Background(3C50)', alpha=0.3)
ax1.errorbar(x_vals, y_tot, fmt='.', label='Net', alpha=0.3)

# 2. モデル
ax1.plot(x_vals, m_vals, label='Best-fit Model', color='red', linewidth=2)

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
residuals = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y_net, m_vals, y_err)]

ax2.errorbar(x_vals, residuals, yerr=1.0, fmt='.', color='black', alpha=0.6)
ax2.axhline(0, color='red', linestyle='--') # ゼロライン
ax2.set_ylabel('(Data-Model)/Error', fontsize=10)
ax2.set_xlabel('Energy (keV)', fontsize=12)
ax2.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
ax2.set_xscale('log')
ax2.grid(True, which="both", ls=":", alpha=0.5)

# 保存
fig.savefig("spectrum_fit.png")
print("\nグラフを 'spectrum_fit.png' に保存しました。")