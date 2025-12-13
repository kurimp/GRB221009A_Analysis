#!/bin/bash

#FILENAMEには"_"を含まないでください。
FILENAME="bin60/from1200to1500"
if [[ "${FILENAME}" == *"_"* ]]; then
  echo '"_" are not allowed in filenames.'
  exit 1
fi

mkdir -p "./data/collect/${FILENAME}"

find -L ./data/* -maxdepth 2 -type f -name ni*_src_bin60.lc

find -L ./data/* -maxdepth 2 -type f -name ni*_src_bin60.lc -exec cp -f {} ./data/collect/${FILENAME}/ \;