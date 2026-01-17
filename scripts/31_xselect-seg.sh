#!/bin/bash

# --- ディレクトリリストの読み込み ---
LIST_DIR=$(yq -r '.segment.path.result_root' scripts/config.yaml)
LIST_NAME=$(yq -r '.segment.path.obs_list_name' scripts/config.yaml)
LIST_FILE="$LIST_DIR/$LIST_NAME"

if [ ! -f "$LIST_FILE" ]; then
  echo "Error: List file '${LIST_FILE}' not found."
  exit 1
fi

echo "Reading ObsIDs from ${LIST_FILE}..."

# --- 設定パラメータ ---
BINSIZE=120
PI_MIN=1200
PI_MAX=1500
# --------------------

echo "Settings: BinSize=${BINSIZE}s, PI=${PI_MIN}-${PI_MAX}"

while IFS=',' read -r obsID segID TimeDataFile _ _
do
  echo "obsID: $obsID, segID: $segID, TimeDataFile: $TimeDataFile"

  if [ "$obsID" == "obsID" ]; then
    continue
  fi
  # 読み込んだ各列を処理

  base_dir="data/obs/${obsID}"
  seg_dir="data/seg/${segID}"

  if [ ! -d "${base_dir}" ]; then
    continue
  fi

  if [ -d "${seg_dir}" ]; then
    rm -r "${seg_dir}"
  fi

  echo "=== Copy obsfiles to segdir ==="
  if [ ! -d "${seg_dir}" ]; then
    mkdir -p "${seg_dir}"/auxil/
    cp -vr "${base_dir}"/auxil/ni"${obsID}".mkf "${seg_dir}"/auxil/
    mkdir -p "${seg_dir}"/xti/event_cl/
    cp -vr "${base_dir}"/xti/event_cl/ni"${obsID}"_0mpu7_cl.evt "${seg_dir}"/xti/event_cl/
    cp -vr "${base_dir}"/xti/event_cl/ni"${obsID}"_0mpu7_ufa.evt "${seg_dir}"/xti/event_cl/
  fi

  echo "=== Extracting LC: ${seg_dir} ==="

  clfile="${seg_dir}/xti/event_cl/ni${obsID}_0mpu7_cl.evt"
  ufafile="${seg_dir}/xti/event_cl/ni${obsID}_0mpu7_ufa.evt"
  evtdir="${seg_dir}/xti/event_cl"

  if [ ! -f "${clfile}" ]; then
    echo "Warning: Cleaned event file not found for ${obsID}."
    echo "         Please run 01_run_nicerl2.sh first."
    continue
  fi

  # 出力ファイル名
  src_lc="${seg_dir}/ni${segID}_src_bin${BINSIZE}_from${PI_MIN}to${PI_MAX}.lc"
  src_cl="${seg_dir}/xti/event_cl/ni${segID}_0mpu7_cl.evt"
  src_pha="${seg_dir}/ni${segID}_src.pha"
  src_ufa="${seg_dir}/xti/event_cl/ni${segID}_0mpu7_ufa.evt"
  rm -f "${src_lc}"

  # xselect セッション設定
  session_name="session_src_${segID}"
  rm -f "${session_name}.xsl"
  clfilename=$(basename "${clfile}")
  ufafilename=$(basename "${ufafile}")
  xselect <<EOF
${session_name}
read event
${evtdir}
${clfilename}
yes
filter time file ${TimeDataFile}
extract events
save events
${src_cl}
yes
extract spectrum
save spectrum
${src_pha}
set binsize ${BINSIZE}
filter pha_cutoff ${PI_MIN} ${PI_MAX}
extract curve exposure=0.0
save curve
${src_lc}
exit
no
EOF
  xselect <<EOF
${session_name}
read event
${evtdir}
${ufafilename}
yes
filter time file ${TimeDataFile}
select events "DET_ID != 14 && DET_ID != 34"
extract events
save events
${src_ufa}
yes
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

done < "$LIST_FILE"

rm -f "xselect.log"