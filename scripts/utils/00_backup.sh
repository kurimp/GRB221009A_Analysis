#!/bin/bash

TODAY_ID=$(date +%y%m%d%H%M%S)

mkdir -p backup/${TODAY_ID}/data/
mkdir -p backup/${TODAY_ID}/results/
mkdir -p backup/${TODAY_ID}/CALDB/

cp -vr data/. backup/${TODAY_ID}/data/
cp -vr results/. backup/${TODAY_ID}/results/
cp -vr CALDB/. backup/${TODAY_ID}/CALDB/
echo "Backup finished!"