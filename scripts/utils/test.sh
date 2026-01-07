#!/bin/bash

cp -r data_container/raw/GRB221009A/. data/obs/

. scripts/01_nicerl2.sh
. scripts/31_xselect-seg.sh
. scripts/04_response.sh
. scripts/05_background.sh
py scripts/20_merge-grp.py
py scripts/21_spectrum.py
