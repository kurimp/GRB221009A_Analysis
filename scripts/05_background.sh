#!/bin/bash

CONFIG="scripts/config.yaml"

LIST_FILE=$(yq -r '.spectrum.path.seg_list' $CONFIG)
data_file_base=$(yq -r '.spectrum.path.base_dir' $CONFIG)

if [ ! -f "$LIST_FILE" ]; then
  echo "Error: List file '${LIST_FILE}' not found."
  exit 1
fi

echo "Reading segIDs from ${LIST_FILE}..."

mapfile -t files < <(grep -vE "^\s*#|^\s*$" "${LIST_FILE}")

echo "  -> Found ${#files[@]} observations."

for segID in "${files[@]}"
do
  base_dir="${data_file_base}/${segID}"

  if [ ! -d "${base_dir}" ]; then
    echo "Skip: ${base_dir} not found. Skipping."
    continue
  fi

  echo "=== Making background files: ${segID} ==="

  obsID=$(echo "$segID" | cut -d'-' -f1)

  #input
  clfile="${base_dir}/xti/event_cl/ni${obsID}_0mpu7_cl.evt"
  src_pha="${base_dir}/ni${segID}_src.pha"
  mkfile="${base_dir}/auxil/ni${obsID}.mkf"
  rmf_outfile="${base_dir}/ni${segID}.rmf"
  skyarffile="${base_dir}/ni${segID}_sky.arf"

  #output
  bkg_3c50="${segID}/ni${segID}_bkg_3c50"
  totspec="${segID}/ni${segID}_tot"
  out_scorp="${base_dir}/ni${segID}_bkg_scorp.pha"

  # --- 1. nibackgen3C50 (3C50モデル) ---
  echo "  [1/2] Running nibackgen3C50..."

  (
    cd "$data_file_base" || { echo "Failed to cd to $DATA_BASE"; exit 1; }

    nibackgen3C50 rootdir="./" \
                  obsid="${segID}" \
                  bkgidxdir="CALDB" \
                  bkglibdir="CALDB" \
                  gainepoch="AUTO" \
                  bkgspec="${bkg_3c50}" \
                  totspec="${totspec}" \
                  dtmin=10.0 dtmax=120.0 \
                  clobber=yes

    # 直前のコマンドの成否($?)をチェック
    if [ $? -eq 0 ]; then
        echo "    -> nibackgen3C50: OK"
    else
        echo "    -> ❌ nibackgen3C50: FAILED"
    fi
  )

  # --- 2. niscorpspect (SCORPEONモデル) ---
  echo "  [2/2] Running niscorpspect..."

  (
    cd ~ || { echo "Failed to cd to $DATA_BASE"; exit 1; }

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
  )

  echo "---------------------------------------------------"
done