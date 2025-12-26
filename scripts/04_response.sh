#!/bin/bash

CONFIG="scripts/config.yaml"

LIST_FILE=$(yq -r '.spectrum.path.seg_list' "$CONFIG")
data_file_base=$(yq -r '.spectrum.path.base_dir' $CONFIG)
ra=$(yq -r '.general.parameters.ra' $CONFIG)
dec=$(yq -r '.general.parameters.dec' $CONFIG)

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
    echo "Error: Directory '${segID}' not found. Skipping."
    continue
  fi

  echo "=== Making response files: ${segID} ==="

  obsID=$(echo "$segID" | cut -d'-' -f1)

  #input
  clfile="${base_dir}/xti/event_cl/ni${obsID}_0mpu7_cl.evt"
  infile="${base_dir}/ni${segID}_src.pha"
  mkfile="${base_dir}/auxil/ni${obsID}.mkf"
  #output
  arf_outfile="${base_dir}/ni${segID}.arf"
  rmf_outfile="${base_dir}/ni${segID}.rmf"
  arf_sky_outfile="${base_dir}/ni${segID}_sky.arf"

  nicerarf infile="${infile}" \
            outfile="${arf_outfile}" \
            attfile="${mkfile}" \
            selfile="${clfile}" \
            ra="${ra}" \
            dec="${dec}" \
            clobber=yes

  nicerrmf infile="${infile}" \
            mkfile="${mkfile}" \
            outfile="${rmf_outfile}" \
            clobber=yes

  nicerarf infile="${infile}" \
            outfile="${arf_sky_outfile}" \
            attfile="${mkfile}" \
            selfile="${clfile}" \
            profile="flat" \
            ra="${ra}" \
            dec="${dec}" \
            clobber=yes

  if [ ! -f "${clfile}" ]; then
    echo "Error: nicerarf and nicerrmf failed for ${segID}."
  else
    echo "  -> nicerarf and nicerrmf completed successfully."
  fi
  echo "---------------------------------------------------"
done