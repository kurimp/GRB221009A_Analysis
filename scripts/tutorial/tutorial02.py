import xspec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

# --- 設定 ---
# 警告抑制
xspec.XspecSettings.allowPrompting = False 
# カイ二乗法
xspec.Fit.statMethod = "chi"
# 試行回数を増やす
xspec.Fit.nIterations = 100

# --- パス設定 ---
obs_dir = "/home/heasoft/data/5420250101"
# 拡張子に注意 (.pha)
files = {
    "data": os.path.join(obs_dir, "ni5420250101_src.pha"),
    "bkg":  os.path.join(obs_dir, "ni5420250101_bkg.pi"),
    "arf":  os.path.join(obs_dir, "ni5420250101.arf"),
    "rmf":  os.path.join(obs_dir, "ni5420250101.rmf")
}

# --- データ読み込み関数 ---
def load_data():
    xspec.AllData.clear()
    xspec.AllModels.clear()
    try:
        s = xspec.Spectrum(files["data"])
        xspec.AllModels.systematic = 0.02  # 系統誤差 1%
        s.background = files["bkg"]
        s.response = files["rmf"]
        s.response.arf = files["arf"]
        s.ignore("**-0.5 10.0-**") # 0.5-10.0keVを使用
        return s
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

# --- フィッティングとプロットを行う関数 ---
def run_fit(model_name, model_def, init_params):
    print(f"\n{'='*40}")
    print(f"Testing Model: {model_name}")
    print(f"{'='*40}")
    
    # モデル定義
    xspec.AllModels.clear()
    m = xspec.Model(model_def)
    
    # 初期値設定
    for param_name, value in init_params.items():
        # "phabs.nH" のように文字列でパラメータを指定して値をセット
        try:
            # param_name (例: "phabs.nH") を評価してオブジェクトを取得
            p = eval(f"m.{param_name}")
            p.values = value
        except Exception as e:
            print(f"Warning: Could not set {param_name}: {e}")

    # フィッティング
    xspec.Fit.query = "yes"
    xspec.Fit.perform()
    
    # 結果取得
    chi2 = xspec.Fit.statistic
    dof = xspec.Fit.dof
    red_chi2 = chi2 / dof if dof > 0 else 0
    
    print(f"Result -> Reduced Chi2: {red_chi2:.4f}")

    # フラックス計算 (2.0 - 10.0 keV)
    # pegpwrlwを使わないモデルもあるため、共通コマンドで計算
    xspec.AllModels.calcFlux("2.0 10.0")
    flux = xspec.AllData(1).flux[0] # [0]は観測フラックス(erg/cm2/s)

    # --- プロット ---
    plot_filename = f"fit_{model_name.replace(' ', '_')}.png"
    
    xspec.Plot.xAxis = "keV"
    xspec.Plot("data")
    
    x_vals = xspec.Plot.x()
    x_err  = xspec.Plot.xErr()
    y_net  = xspec.Plot.y()
    y_err  = xspec.Plot.yErr()
    m_vals = xspec.Plot.model()
    
    # 残差計算
    residuals = [(y - m) / e if e > 0 else 0 for y, m, e in zip(y_net, m_vals, y_err)]

    # 描画
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, 
                                   gridspec_kw={'height_ratios': [3, 1], 'hspace': 0.05})
    
    # スペクトル
    ax1.errorbar(x_vals, y_net, xerr=x_err, yerr=y_err, fmt='.', color='blue', label='Data', alpha=0.5)
    ax1.plot(x_vals, m_vals, color='red', label=f'Model: {model_name}', linewidth=2)
    ax1.set_yscale('log')
    ax1.set_ylabel('Counts s$^{-1}$ keV$^{-1}$')
    ax1.set_title(f'Model: {model_name}\nRed.Chi2: {red_chi2:.2f}, Flux(2-10k): {flux:.2e}')
    ax1.legend()
    ax1.grid(True, which="both", ls=":", alpha=0.5)
    
    # 残差
    ax2.errorbar(x_vals, residuals, yerr=1.0, fmt='.', color='black', alpha=0.6)
    ax2.axhline(0, color='red', linestyle='--')
    ax2.set_ylabel('Residuals')
    ax2.set_xlabel('Energy (keV)')
    ax2.set_ylim(-5, 5)
    ax2.set_xscale('log')
    ax2.grid(True, which="both", ls=":", alpha=0.5)
    
    plt.savefig(plot_filename)
    plt.close()
    
    return red_chi2, flux, plot_filename

# ==========================================
# メイン処理：比較ループ
# ==========================================

# データロード
s = load_data()

# 比較したいモデルのリスト
# (名前, XSPEC定義式, 初期パラメータ辞書)
models_to_test = [
    (
        "Power Law", 
        "phabs*powerlaw", 
        {"phabs.nH": 1.0, "powerlaw.PhoIndex": 1.5, "powerlaw.norm": 1.0}
    ),
    (
        "Cutoff Power Law", 
        "phabs*cutoffpl", 
        {"phabs.nH": 1.0, "cutoffpl.PhoIndex": 1.0, "cutoffpl.HighECut": 5.0, "cutoffpl.norm": 1.0}
    ),
    (
        "Blackbody + PL", 
        "phabs*(powerlaw+bbody)", 
        {"phabs.nH": 1.0, "powerlaw.PhoIndex": 2.0, "powerlaw.norm": 1.0, "bbody.kT": 1.0, "bbody.norm": 0.1}
    )
]

results = []

print("\n=== Starting Multi-Model Fit ===")

for name, definition, params in models_to_test:
    r_chi2, r_flux, r_img = run_fit(name, definition, params)
    results.append((name, r_chi2, r_flux, r_img))

# === 最終結果のサマリー表示 ===
print("\n" + "="*60)
print(f"{'Model Name':<25} | {'Red. Chi2':<10} | {'Flux (2-10 keV)':<15}")
print("-" * 60)

best_model = None
min_chi2 = 99999

for name, chi2, flux, img in results:
    print(f"{name:<25} | {chi2:<10.4f} | {flux:<15.2e}")
    if abs(chi2 - 1.0) < abs(min_chi2 - 1.0): # 1.0に最も近いものを探す
        min_chi2 = chi2
        best_model = name

print("-" * 60)
print(f"Best Model (closest to 1.0): {best_model}")
print("Check the saved .png files for visual inspection.")