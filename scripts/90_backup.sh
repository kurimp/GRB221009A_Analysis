#!/bin/bash

TODAY_ID=$(date +%y%m%d%H%M%S)
cp -vr GRB221009A/ backup/${TODAY_ID}/
cp -vr CALDB/ backup/${TODAY_ID}/
echo "Backup finished!"