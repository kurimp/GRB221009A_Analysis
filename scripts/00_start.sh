#!/bin/bash

if [ -z "$1" ]; then
  echo "Error:Input the directory name of the object."
  exit 1
fi

obj_dir=$1

if [ -d "$obj_dir" ]; then
  docker run -it --rm \
  --net=host \
  -v ./$obj_dir/data_NICER:/home/heasoft/data \
  -v ./CALDB:/home/heasoft/CALDB \
  -e DISPLAY=$DISPLAY \
  heasoft:v6.36 \
  bash -c 'echo "export CALDB=/home/heasoft/CALDB" >> ~/.bashrc && echo "export GEOMAG_PATH=/home/heasoft/CALDB/data/gen/pcf/geomag" >> ~/.bashrc && exec bash'
else
  echo "There are no such directory..."
  exit 1
fi