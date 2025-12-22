#!/bin/bash

CONFIG="scripts/config.yaml"

is_obs_seg=$(yq -r '.segment.parameters.is_obs_seg' $CONFIG)
BIN=$(yq -r '.segment.parameters.BIN' $CONFIG)
PI_MIN=$(yq -r '.segment.parameters.PI_MIN' $CONFIG)
PI_MAX=$(yq -r '.segment.parameters.PI_MAX' $CONFIG)
collect_dir=$(yq -r '.segment.path.collect_dir' $CONFIG)

result_root=$(yq -r '.segment.path.result_root' $CONFIG)
obs_list_name=$(yq -r '.segment.path.obs_list_name' $CONFIG)
obs_list_path="${result_root}/${obs_list_name}"

FILENAME="${collect_dir}/bin${BIN}/from${PI_MIN}to${PI_MAX}"

if [[ "${FILENAME}" == *"_"* ]]; then
  echo '"_" are not allowed in filenames.'
  exit 1
fi

rm -r "./data/collect/${FILENAME}"

mkdir -p "./data/collect/${FILENAME}"

seg_list=$(awk -F',' 'NR>1 {print $2}' "$obs_list_path" | tr -d '\r')

count=0
for segID in $seg_list; do
  # IDが空でないか確認
  [ -z "$segID" ] && continue
  
  echo "🔍 Searching for segID: $segID"
  
  find -L "./data/${is_obs_seg}" -maxdepth 2 -type f \
    -name "ni${segID}_src_bin${BIN}_from${PI_MIN}to${PI_MAX}.lc"
  
  find -L "./data/${is_obs_seg}" -maxdepth 2 -type f \
    -name "ni${segID}_src_bin${BIN}_from${PI_MIN}to${PI_MAX}.lc" \
    -exec cp -f {} "./data/collect/${FILENAME}" \;
done