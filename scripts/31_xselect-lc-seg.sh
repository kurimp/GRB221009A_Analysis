#!/bin/bash

# --- ディレクトリリストの読み込み ---
LIST_FILE="results/lightcurve/segments/segInfo_fixed.csv"

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

while IFS=',' read -r obsID segID TimeDataFile col4 col5
do
  echo "obsID: $obsID, segID: $segID, TimeDataFile: $TimeDataFile"
  
  if [ $obsID == "obsID" ]; then
    continue
  fi
  # 読み込んだ各列を処理
  
  base_dir="data/obs/${obsID}"
  seg_dir="data/seg/${segID}"
  
  if [ ! -d "${base_dir}" ]; then
    continue
  fi
  
  echo "=== Copy obsfiles to segdir ==="
  if [ ! -d "${seg_dir}" ]; then
    mkdir -p ${seg_dir}/auxil/
    cp -vr ${base_dir}/auxil/ni${obsID}.mkf ${seg_dir}/auxil/
    mkdir -p ${seg_dir}/xti/event_cl/
    cp -vr ${base_dir}/xti/event_cl/ni${obsID}_0mpu7_cl.evt ${seg_dir}/xti/event_cl/
  fi
  
  echo "=== Extracting LC: ${seg_dir} ==="
  
  clfile="${seg_dir}/xti/event_cl/ni${obsID}_0mpu7_cl.evt"
  evtdir="${seg_dir}/xti/event_cl"

  # nicerl2が完了しているか確認
  if [ ! -f "${clfile}" ]; then
    echo "Warning: Cleaned event file not found for ${obsID}."
    echo "         Please run 01_run_nicerl2.sh first."
    continue
  fi

  # 出力ファイル名
  src_lc="${seg_dir}/ni${segID}_src_bin${BINSIZE}_from${PI_MIN}to${PI_MAX}.lc"
  src_evt="${seg_dir}/xti/event_cl/ni${segID}_0mpu7_cl.evt"
  rm -f "${src_lc}"
  
  
  # xselect セッション設定
  session_name="session_src_${segID}"
  rm -f "${session_name}.xsl"
  clfilename=$(basename "${clfile}")
  if [ ! -f "${src_evt}" ]; then
    xselect <<EOF
${session_name}
read event
${evtdir}
${clfilename}
yes
filter time file ${TimeDataFile}
extract events
save events
${src_evt}
yes
set binsize ${BINSIZE}
filter pha_cutoff ${PI_MIN} ${PI_MAX}
extract curve exposure=0.0
save curve
${src_lc}
exit
no
EOF
  else
    xselect <<EOF
${session_name}
read event
${evtdir}
${clfilename}
yes
filter time file ${TimeDataFile}
extract events
save events
${src_evt}
yes
yes
set binsize ${BINSIZE}
filter pha_cutoff ${PI_MIN} ${PI_MAX}
extract curve exposure=0.0
save curve
${src_lc}
exit
no
EOF
  fi
  rm -f "${session_name}.xsl"

  if [ -f "${src_lc}" ]; then
    echo "  -> Success: Created ${src_lc}"
  else
    echo "Warning: Lightcurve creation failed (likely empty data)."
  fi

  echo "---------------------------------------------------"
  
done < "$LIST_FILE"

rm -f "xselect.log"