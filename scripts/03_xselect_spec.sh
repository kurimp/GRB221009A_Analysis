#!/bin/bash

# --- ディレクトリリストの読み込み ---
LIST_FILE="scripts/obs_list.txt"

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

for obs_dir in "${files[@]}"
do
  
  base_dir="data/${obs_dir}"
  
  if [ ! -d "${base_dir}" ]; then
    continue
  fi

  echo "=== Extracting spectrum: ${obs_dir} ==="
  
  clfile="${base_dir}/xti/event_cl/ni${obs_dir}_0mpu7_cl.evt"
  evtdir="${base_dir}/xti/event_cl"

  # nicerl2が完了しているか確認
  if [ ! -f "${clfile}" ]; then
    echo "Warning: Cleaned event file not found for ${obs_dir}."
    echo "         Please run 01_nicerl2.sh first."
    continue
  fi

  # 出力ファイル名
  src_spec="${base_dir}/ni${obs_dir}_src.pha"
  rm -f "${src_spec}"

  # xselect セッション設定
  session_name="session_spec_${obs_dir}"
  rm -f "${session_name}.xsl"
  clfilename=$(basename "${clfile}")

  xselect <<EOF
${session_name}
read event
${evtdir}
${clfilename}
yes
extract spectrum
save spectrum
${src_spec}
exit
no
EOF
  rm -f "${session_name}.xsl"

  if [ -f "${src_spec}" ]; then
     echo "  -> Success: Created ${src_spec}"
  else
     echo "Warning: Spectrum creation failed (likely empty data)."
  fi

  echo "---------------------------------------------------"
done