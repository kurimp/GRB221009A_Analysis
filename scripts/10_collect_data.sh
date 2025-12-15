#!/bin/bash

BIN=120
PI_MIN=1200
PI_MAX=1500

FILENAME="bin${BIN}/from${PI_MIN}to${PI_MAX}"

if [[ "${FILENAME}" == *"_"* ]]; then
  echo '"_" are not allowed in filenames.'
  exit 1
fi

mkdir -p "./data/collect/${FILENAME}"

find -L ./data/* -maxdepth 2 -type f -name ni*_src_bin${BIN}_from${PI_MIN}to${PI_MAX}.lc -exec cp -f {} ./data/collect/${FILENAME}/ \;