#!/bin/bash

# --- 引数処理 (-f フラグの確認) ---
FORCE_MODE="false"

for arg in "$@"
do
  if [ "$arg" == "-f" ]; then
    FORCE_MODE="true"
    echo "!!! Force mode enabled: nicerarf and nicerrmf will be re-run for all observations!!!"
  fi
done

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
  
  base_dir="data/obs/${obs_dir}"
  
  if [ ! -d "${base_dir}" ]; then
    echo "Error: Directory '${obs_dir}' not found. Skipping."
    continue
  fi
  
  echo "=== Making response files: ${obs_dir} ==="
  
  clfile="${base_dir}/xti/event_cl/ni${obs_dir}_0mpu7_cl.evt"
  infile="${base_dir}/ni${obs_dir}_src.pha"
  mkfile="${base_dir}/auxil/ni${obs_dir}.mkf"
  arf_outfile="${base_dir}/ni${obs_dir}.arf"
  rmf_outfile="${base_dir}/ni${obs_dir}.rmf"
  arf_sky_outfile="${base_dir}/ni${obs_dir}_sky.arf"
  ra=288.2643
  dec=19.7712
  
  
  # ファイルが存在し、かつ強制モードでない(false)場合のみスキップ
  if [ -f "${arf_outfile}" ] && [ -f "${rmf_outfile}" ] && [ -f "${arf_sky_outfile}" ] && [ "${FORCE_MODE}" = "false" ]; then
    echo "  -> Found response files. Skipping."
  else
    if [ "${FORCE_MODE}" = "true" ]; then
      echo "  -> Force mode: Re-running nicerarf and nicerrmf..."
    else
      echo "  -> Response files not found. Running..."
    fi
    
    nicerarf infile=${infile} \
             outfile=${arf_outfile} \
             attfile=${mkfile} \
             selfile=${clfile} \
             ra=${ra} \
             dec=${dec} \
             clobber=yes
    
    nicerrmf infile=${infile} \
             mkfile=${mkfile} \
             outfile=${rmf_outfile} \
             clobber=yes
    
    nicerarf infile=${infile} \
             outfile=${arf_sky_outfile} \
             attfile=${mkfile} \
             selfile=${clfile} \
             profile="flat" \
             ra=${ra} \
             dec=${dec} \
             clobber=yes
    
    if [ ! -f "${clfile}" ]; then
      echo "Error: nicerarf and nicerrmf failed for ${obs_dir}."
    else
      echo "  -> nicerarf and nicerrmf completed successfully."
    fi
  fi
  echo "---------------------------------------------------"
done