import os
import sys
import subprocess
import pandas as pd
from scripts.utils.read_config import cfg

# --- 設定読み込み ---
base_dir = cfg['spectrum']['path']['base_dir']
grp_time = cfg['spectrum']['parameters']['grp_time']
merge_list = cfg['spectrum']['path']['merge_list']

# 出力ディレクトリ (絶対パス)
merged_root = cfg['spectrum']['path']['merge_name']
output_dir = os.path.join(cfg['spectrum']['path']['merge_output'], merged_root)
os.makedirs(output_dir, exist_ok=True)


if not os.path.exists(merge_list):
  print(f"❌ Error: Merge list not found: {merge_list}")
  sys.exit(1)

df = pd.read_csv(merge_list, header=None, names=['segID'], comment='#')
print(df)

src_files = []
bkg_files = []
rmf_files = []
arf_files = []

valid_count = 0

print("\nScanning segments...")
for _, row in df.iterrows():
  segID = str(row['segID']).strip()
  dir_path = os.path.join(base_dir, segID)

  # ファイルパス (絶対パスに変換)
  src_path = os.path.abspath(os.path.join(dir_path, f"ni{segID}_src.pha"))
  rmf_path = os.path.abspath(os.path.join(dir_path, f"ni{segID}.rmf"))
  arf_path = os.path.abspath(os.path.join(dir_path, f"ni{segID}.arf"))

  # バックグラウンドファイル (.pi または .pha を探す)
  bkg_candidates = [
    os.path.abspath(os.path.join(dir_path, f"ni{segID}_bkg_3c50.pi")),
    os.path.abspath(os.path.join(dir_path, f"ni{segID}_bkg_3c50.pha"))
  ]
  bkg_path = None
  for cand in bkg_candidates:
    if os.path.exists(cand):
      bkg_path = cand
      break

  # ファイル存在確認
  if os.path.exists(src_path) and bkg_path and os.path.exists(rmf_path) and os.path.exists(arf_path):

    lname_src = f"seg{valid_count:03d}_src.pha"
    lname_bkg = f"seg{valid_count:03d}_bkg.pha"
    lname_rmf = f"seg{valid_count:03d}.rmf"
    lname_arf = f"seg{valid_count:03d}.arf"

    def create_link(target, link_name):
      link_path = os.path.join(output_dir, link_name)
      if os.path.exists(link_path) or os.path.islink(link_path):
        os.remove(link_path)
      os.symlink(target, link_path)
      return link_name # パスを含まないファイル名を返す

    src_files.append(create_link(src_path, lname_src))
    bkg_files.append(create_link(bkg_path, lname_bkg))
    rmf_files.append(create_link(rmf_path, lname_rmf))
    arf_files.append(create_link(arf_path, lname_arf))
    print(f"  OK: {segID}")
    valid_count += 1
  else:
    print(f"  [SKIP] {segID} (Files missing)")

if valid_count == 0:
  print("No segments found.")
  sys.exit(1)

print(f"Found {valid_count} segments.")

# --- リストファイルの作成 ---
temp_list_name = "temp_addascaspec_list.txt"
temp_file_path = os.path.join(output_dir, temp_list_name)

with open(temp_file_path, 'w') as f:
  f.write(" ".join(src_files) + "\n")
  f.write(" ".join(bkg_files) + "\n")
  f.write(" ".join(rmf_files) + "\n")
  f.write(" ".join(arf_files) + "\n")

print(f"Created list file: {temp_file_path}")

# --- 3. addascaspec の実行 ---
print("\n=== Running addascaspec ===")

# ファイル名定義 (パスを含まない)
out_pha_name = f"{merged_root}.pha"
out_rsp_name = f"{merged_root}.rsp"
out_bkg_name = f"{merged_root}_bkg_3c50.pha"

# 既存削除
for name in [out_pha_name, out_rsp_name, out_bkg_name]:
  path = os.path.join(output_dir, name)
  if os.path.exists(path):
    os.remove(path)

# ★重要修正: infileには「ファイル名」だけを渡し、cwdでその場所に移動して実行する
cmd = [
  "addascaspec",
  f"{temp_list_name}",  # ディレクトリパスを含めない
  f"{out_pha_name}",
  f"{out_rsp_name}",
  f"{out_bkg_name}"
]

try:
  subprocess.run(cmd, check=True, cwd=output_dir)
  print("-> addascaspec finished successfully.")
except subprocess.CalledProcessError:
  print("❌ addascaspec failed.")
  sys.exit(1)

# --- 4. grppha の実行 ---
print("\n=== Running grppha ===")
out_grp_name = f"{merged_root}_grp.pha"
out_grp_path = os.path.join(output_dir, out_grp_name)

if os.path.exists(out_grp_path):
  os.remove(out_grp_path)

grppha_input = (
  f"chkey BACKFILE {out_bkg_name}\n"
  f"chkey RESPFILE {out_rsp_name}\n"
  f"group min {grp_time}\n"
  f"exit\n"
)

try:
  subprocess.run(
    ["grppha", f"infile={out_pha_name}", f"outfile={out_grp_name}", "clobber=yes"],
    input=grppha_input,
    text=True,
    cwd=output_dir, # ここも cwd を指定
    check=True
  )
  print(f"\n✅ Created: {out_grp_path}")


  for f in src_files + bkg_files + rmf_files + arf_files:
    try:
      os.remove(os.path.join(output_dir, f))
    except:
      pass

except subprocess.CalledProcessError:
  print("❌ grppha failed.")
  sys.exit(1)