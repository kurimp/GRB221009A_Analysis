#!/bin/bash

# --- ディレクトリリストの読み込み ---
LIST_FILE="obs_list.txt"

if [ ! -f "$LIST_FILE" ]; then
  echo "Error: List file '${LIST_FILE}' not found."
  exit 1
fi

echo "Reading ObsIDs from ${LIST_FILE}..."

# コメント行(#)と空行を除外して配列に読み込む
# grep -vE "^\s*#|^\s*$" : #で始まる行と空行を除外
files=($(grep -vE "^\s*#|^\s*$" "${LIST_FILE}"))

# 読み込んだ数の確認
echo "  -> Found ${#files[@]} observations."

# --- 設定パラメータ (ここを変えて何度でも実行可能) ---
BINSIZE=60
PI_MIN=30    # 0.3 keV
PI_MAX=1000  # 10.0 keV
# --------------------

echo "Settings: BinSize=${BINSIZE}s, PI=${PI_MIN}-${PI_MAX}"

for obs_dir in "${files[@]}"
do
  if [ ! -d "${obs_dir}" ]; then
    continue
  fi

  echo "=== Extracting LC: ${obs_dir} ==="
  
  base_dir="data/${obs_dir}"
  
  clfile="${base_dir}/xti/event_cl/ni${obs_dir}_0mpu7_cl.evt"
  evtdir="${base_dir}/xti/event_cl"

  # nicerl2が完了しているか確認
  if [ ! -f "${clfile}" ]; then
    echo "Warning: Cleaned event file not found for ${obs_dir}."
    echo "         Please run 01_run_nicerl2.sh first."
    continue
  fi

  # 出力ファイル名
  src_lc="${base_dir}/ni${obs_dir}_src_bin${BINSIZE}.lc"
  rm -f "${src_lc}"

  # xselect セッション設定
  session_name="session_src_${obs_dir}"
  rm -f "${session_name}.xsl"
  clfilename=$(basename "${clfile}")

  xselect <<EOF
${session_name}
read event
${evtdir}
${clfilename}
yes
set binsize ${BINSIZE}
filter pha_cutoff ${PI_MIN} ${PI_MAX}
extract curve exposure=0.0
save curve
${src_lc}
exit
no
EOF
  rm -f "${session_name}.xsl"

  if [ -f "${src_lc}" ]; then
     echo "  -> Success: Created ${src_lc}"
  else
     echo "Warning: Lightcurve creation failed (likely empty data)."
  fi

  echo "---------------------------------------------------"
done