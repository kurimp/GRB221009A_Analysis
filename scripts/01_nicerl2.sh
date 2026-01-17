#!/bin/bash

# --- 引数処理 (-f フラグの確認) ---
FORCE_MODE="false"

for arg in "$@"
do
  if [ "$arg" == "-f" ]; then
    FORCE_MODE="true"
    echo "!!! Force mode enabled: nicerl2 will be re-run for all observations. !!!"
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

  echo "=== Processing nicerl2: ${obs_dir} ==="

  clfile="${base_dir}/xti/event_cl/ni${obs_dir}_0mpu7_cl.evt"

  # ファイルが存在し、かつ強制モードでない(false)場合のみスキップ
  if [ -f "${clfile}" ] && [ "${FORCE_MODE}" = "false" ]; then
    echo "  -> Found clean event file. Skipping nicerl2."
  else
    if [ "${FORCE_MODE}" = "true" ]; then
      echo "  -> Force mode: Re-running nicerl2..."
    else
      echo "  -> Clean event file not found. Running nicerl2..."
    fi

    # NICERL2実行
    # GRB解析用にフィルタ条件を大幅に緩和しています
    nicerl2 indir="${base_dir}" \
            clobber=YES \
            filtcolumns=NICERV6 \
            detlist="launch,-14,-34"

    if [ ! -f "${clfile}" ]; then
      echo "Error: nicerl2 failed for ${obs_dir}."
    else
      echo "  -> nicerl2 completed successfully."
    fi
  fi
  echo "---------------------------------------------------"
done