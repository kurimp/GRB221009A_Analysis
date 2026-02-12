import numpy as np
from astropy.io import fits
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.size": 24,           # 全体の基本フォントサイズ
    "axes.titlesize": 22,      # グラフタイトルのサイズ
    "axes.labelsize": 20,      # 軸ラベルのサイズ
    "xtick.labelsize": 24,     # x軸目盛りのサイズ
    "ytick.labelsize": 24,     # y軸目盛りのサイズ
    "legend.fontsize": 16,     # 凡例のサイズ
    "lines.linewidth": 3,      # プロット線の太さ
    "lines.markersize": 10,    # マーカーの大きさ
    "axes.linewidth": 2,       # グラフ枠線の太さ
    "xtick.major.width": 2,    # 目盛り線の太さ
    "ytick.major.width": 2,
    "savefig.dpi": 300         # 保存時の解像度（高めに設定）
})

def read_arf(filename):
    with fits.open(filename) as hdul:
        data = hdul[1].data
        elo = data['ENERG_LO']
        ehi = data['ENERG_HI']
        area = data['SPECRESP']
    energy = 0.5 * (elo + ehi)  # bin中心
    return energy, area

# ARF読み込み
e_nicer, a_nicer = read_arf("nixtiaveonaxis20170601v005.arf")
e_xrt_pc, a_xrt_pc = read_arf("swxpc0to12s6_20010101v013.arf")
e_xrt_wt, a_xrt_wt = read_arf("swxwt0to2s6_20010101v014.arf")

a_nicer_interp_pc = np.interp(e_xrt_pc, e_nicer, a_nicer)
a_nicer_interp_wt = np.interp(e_xrt_wt, e_nicer, a_nicer)

# 比
ratio_pc = a_nicer_interp_pc / a_xrt_pc
ratio_wt = a_nicer_interp_wt / a_xrt_wt

# プロット
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]}, constrained_layout=True)
plt.subplots_adjust(hspace=0.0)

ax1.plot(e_nicer, a_nicer, label="NICER")
ax1.fill_between(e_nicer, a_nicer, y2=0, alpha=0.3)
ax1.plot(e_xrt_wt, a_xrt_wt, label="Swift-XRT(WT mode)", color="C1")
ax1.fill_between(e_xrt_wt, a_xrt_wt, y2=0, alpha=0.3, color="C1")
#ax1.plot(e_xrt_pc, a_xrt_pc, label="Swift-XRT(PC mode)", color="C2")
#ax1.fill_between(e_xrt_pc, a_xrt_pc, y2=0, alpha=0.3, color="C2")

ax2.plot(e_xrt_wt, ratio_wt, label="NICER/Swift-XRT(WT mode)", color="C1")
#ax2.plot(e_xrt_pc, ratio_pc, label="NICER/Swift-XRT(PC mode)", color="C2")

#ax1.axvline(5.56, color="black", linestyle='--', alpha=0.5, label="Fe(E=5.560 keV)")
#ax2.axvline(5.56, color="black", linestyle='--', alpha=0.5, label="Fe(E=5.560 keV)")

ax1.set_ylabel("Effective Area (cm$^2$)")
ax1.set_xlim(0.1, 11)
ax1.set_ylim(0, 2100)
ax1.set_xscale('log')
ax1.grid(True, which='both', axis='both', linestyle='--', alpha=0.3)
ax1.legend()

ax2.axhline(0, color="black", linestyle='-')
ax2.set_xlabel("Energy (keV)")
ax2.set_ylabel("Ratio")
ax2.set_ylim(-5, 25)
ax2.grid(True, which='both', axis='both', linestyle='--', alpha=0.3)
ax2.legend()

plt.tight_layout()

fig.savefig("EffectiveArea.png")
