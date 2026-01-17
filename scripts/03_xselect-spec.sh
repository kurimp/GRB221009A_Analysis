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
    continue
  fi

  echo "=== Extracting spectrum: ${segID} ==="

  clfile="${base_dir}/xti/event_cl/ni${segID}_0mpu7_cl.evt"
  evtdir="${base_dir}/xti/event_cl"

  if [ ! -f "${clfile}" ]; then
    echo "Warning: Cleaned event file not found for ${segID}."
    echo "         Please run 01_nicerl2.sh first."
    continue
  fi

  # 出力ファイル名
  src_spec="${base_dir}/ni${segID}_src.pha"
  rm -f "${src_spec}"

  # xselect セッション設定
  session_name="session_spec_${segID}"
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