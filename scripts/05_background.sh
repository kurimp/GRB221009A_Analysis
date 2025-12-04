#!/bin/bash

# --- 引数処理 ---
FORCE_MODE="false"
for arg in "$@"
do
  if [ "$arg" == "-f" ]; then
    FORCE_MODE="true"
    echo "!!! Force mode enabled !!!"
  fi
done

# --- リスト読み込み ---
LIST_FILE="scripts/obs_list.txt"
if [ ! -f "$LIST_FILE" ]; then
  echo "Error: List file '${LIST_FILE}' not found."
  exit 1
fi
files=($(grep -vE "^\s*#|^\s*$" "${LIST_FILE}"))

# --- メインループ ---
for obs_dir in "${files[@]}"
do
  base_dir="data/${obs_dir}"
  
  if [ ! -d "${base_dir}" ]; then
    echo "Skip: ${base_dir} not found."
    continue
  fi
  
  echo "=== Making background files: ${obs_dir} ==="
  
  # ファイルパス定義
  clfile="${base_dir}/xti/event_cl/ni${obs_dir}_0mpu7_cl.evt"
  src_pha="${base_dir}/ni${obs_dir}_src.pha"
  mkfile="${base_dir}/auxil/ni${obs_dir}.mkf"
  rmf_outfile="${base_dir}/ni${obs_dir}.rmf"
  skyarffile="${base_dir}/ni${obs_dir}_sky.arf"
  
  # 出力ファイル名
  bkg_3c50="${obs_dir}/ni${obs_dir}_bkg_3c50"
  out_scorp="${base_dir}/ni${obs_dir}_bkg_scorp.pha"

  # --- 1. nibackgen3C50 (3C50モデル) ---
  echo "  [1/2] Running nibackgen3C50..."
  
  cd data
  
  nibackgen3C50 rootdir="./" \
                obsid=${obs_dir} \
                bkgidxdir="CALDB" \
                bkglibdir="CALDB" \
                gainepoch="AUTO" \
                bkgspec="${bkg_3c50}" \
                totspec="${obs_dir}/ni${obs_dir}_tot" \
                dtmin=10.0 dtmax=120.0 \
                clobber=yes

  # 直前のコマンドの成否($?)をチェック
  if [ $? -eq 0 ]; then
      echo "    -> nibackgen3C50: OK"
  else
      echo "    -> ❌ nibackgen3C50: FAILED"
  fi

  # --- 2. niscorpspect (SCORPEONモデル) ---
  echo "  [2/2] Running niscorpspect..."
  
  cd ..
  
  niscorpspect infile="${src_pha}" \
               outfile="${out_scorp}" \
               mkfile="${mkfile}" \
               selfile="${clfile}" \
               skyarffile="${skyarffile}" \
               specrespfile="${rmf_outfile}" \
               clobber=yes
               
  if [ $? -eq 0 ]; then
      echo "    -> niscorpspect: OK"
  else
      echo "    -> ❌ niscorpspect: FAILED"
  fi
  
  echo "---------------------------------------------------"
done