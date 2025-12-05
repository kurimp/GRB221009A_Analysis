import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import csv

ObsID = "5420250101"

def treatment(ObsID, bkgtype="3c50"):
  xspec.AllData.clear()
  xspec.AllModels.clear()

  xspec.Fit.statMethod = "chi"
  obs_directory = os.path.join("/home/heasoft/data", ObsID)
  data_filename = f"ni{ObsID}_src.pha"
  arf_filename = f"ni{ObsID}.arf"
  rmf_filename = f"ni{ObsID}.rmf"
  if bkgtype == "3c50":
    bkg_filename = f"ni{ObsID}_bkg_3c50.pi"
  elif bkgtype == "scorpion":
    bkg_filename = f"ni{ObsID}_bkg_scorp.pha"
  else:
    print("bkgtype must be either '3c50' or 'scorpion'.")

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
  print("\n--- 2. Defining Model ---")
  m = xspec.Model("phabs * powerlaw")
  
  # パラメータ1: nH (10^22 cm^-2)
  # 値, 変化幅, 最小値, 底値, 天井値, 最大値
  m(1).values = "0.1 0.01 0.0 0.0 100.0 100.0"
  
  # パラメータ2: Photon Index (Gamma)
  m(2).values = "1.7 0.1 0.0 0.0 10.0 10.0"
  
  # パラメータ3: Norm
  # 値を1.0にするが、直後にrenormを行うため仮置き
  m(3).values = "1.0 0.01 0.0 0.0 1e10 1e10"
  
  print("--- Initial Parameters ---")
  m.show()

  # ★修正: フィッティング前にデータの強度レベルにモデルを合わせる
  print("--- Pre-adjusting Normalization ---")
  xspec.Fit.renorm()
  m.show() # renorm後の値を確認
  
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
  m_vals = xspec.Plot.model()

  xspec.Plot('Background')
  y_bkg  = xspec.Plot.y()

  y_tot = [n + b for n, b in zip(y_net, y_bkg)]
  
  return ObsID, bkgtype, x_vals, x_err, y_net, y_err, y_bkg, y_tot, m_vals, red_chi2

# Matplotlibで描画
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
plt.subplots_adjust(hspace=0.0)

for bkgtype in ["3c50", "scorpion"]:
  if bkgtype=="scorpion":
    pass
  ObsID, bkgtype, x_vals, x_err, y_net, y_err, y_bkg, y_tot, m_vals, red_chi2 = treatment(ObsID, bkgtype)
  
  # 1. 観測データ (対数軸の方が見やすい場合が多いです)
  ax1.errorbar(x_vals, y_tot, fmt='.', label='Total', alpha=0.3)
  ax1.errorbar(x_vals, y_net, yerr=y_err, fmt='.', label=f'Net({bkgtype})', alpha=0.3)
  ax1.step(x_vals, y_bkg, where='mid', label=f'Background({bkgtype})', alpha=0.3)
  
  # 2. モデル
  ax1.plot(x_vals, m_vals, label=f'Best-fit Model({bkgtype})(Reduced chi2:{red_chi2:.2f})', linewidth=2)
  
  # --- 下段: 残差 (Residuals) ---
  # (データ - モデル) / 誤差 = シグマ単位のズレ
  residuals = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y_net, m_vals, y_err)]
  
  row_data = list(zip(*[x_vals, y_tot, y_net, m_vals, y_err]))
  ax2.errorbar(x_vals, residuals, fmt='.', alpha=0.6, label=f"esiduals({bkgtype})")
  import csv
  with open(f'results/result({bkgtype}).csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['x_vals', 'y_tot', 'y_net', 'm_vals', 'y_err'])
    writer.writerows(row_data)

fig.suptitle(f'GRB221009A NICER Spectrum Fit')

ax1.set_xscale('log')
ax1.set_yscale('log')
#ax1.set_xlabel('Energy (keV)')
ax1.set_ylabel('Counts s$^{-1}$ keV$^{-1}$')
ax1.legend()
ax1.grid(True, which="both", ls="--", alpha=0.3)

ax2.axhline(0,color="black", linestyle='--', alpha=0.5)
ax2.set_xscale('log')
ax2.set_ylabel('(Data-Model)/Error')
ax2.set_xlabel('Energy (keV)')
#ax2.set_ylim(-5, 5) # ズレの表示範囲 (±5シグマ)
ax2.legend()
ax2.grid(True, which="both", ls=":", alpha=0.5)

# 保存
fig.savefig("results/spectrum_fit.png")
print("\nグラフを 'results/spectrum_fit.png' に保存しました。")