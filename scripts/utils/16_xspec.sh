#!/bin/bash

dataname="5420250101-000/ni5420250101-000_grp_gm100.pha"

xspec <<EOF
data ${dataname}
ignore **-4.0 10.0-**
model tbabs*ztbabs*powerlaw
0.538 -1
1.29 -1
0.151 -1
1.8
1.0
fit
error 4
cpd /xs
setplot energy
setplot background
plot ldata delchi
EOF