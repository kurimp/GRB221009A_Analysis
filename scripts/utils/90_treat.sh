#!/bin/bash

obsID="5420250101"
segID="5420250101-000"
gpmin=40
ign="**-1.0 8.0-**"

rm -rf *

cp /workspaces/HEASoft/results/lightcurve/segments/time_fixed/${segID}.txt .
cp -r /workspaces/HEASoft/data_container/raw/GRB221009A/${obsID} .

nicerl2 indir="${obsID}" clobber=YES filtcolumns=NICERV6 detlist="launch,-14,-34"

mv ${obsID} ${segID}

xselect <<EOF
manual_${segID}_cl
read event
${segID}
xti/event_cl/ni${obsID}_0mpu7_cl.evt
yes
filter time file ${segID}.txt
extract events
save events
${segID}/xti/event_cl/ni${segID}_0mpu7_cl.evt
yes
extract spectrum
save spectrum
${segID}/ni${segID}_src.pha
set binsize 120
filter pha_cutoff 400 800
extract curve exposure=0.0
save curve
${segID}/ni${segID}.lc
exit
no
EOF

xselect <<EOF
manual_${segID}_ufa
read event
${segID}
xti/event_cl/ni${obsID}_0mpu7_ufa.evt
yes
extract events
filter time file ${segID}.txt
extract event
select events "DET_ID != 14 && DET_ID != 34"
save events
${segID}/xti/event_cl/ni${segID}_0mpu7_ufa.evt
yes
exit
no
EOF

rm -f xsel_timefile.asc
rm -f xselect.log

nicerarf \
  infile="${segID}/ni${segID}_src.pha" \
  ra=288.2643 \
  dec=19.7712 \
  detlist="launch,-14,-34" \
  selfile="${segID}/auxil/ni${obsID}.mkf" \
  attfile="${segID}/auxil/ni${obsID}.mkf" \
  outfile="${segID}/ni${segID}.arf" \
  clobber=yes

nicerrmf \
  infile="${segID}/ni${segID}_src.pha" \
  mkfile="${segID}/auxil/ni${obsID}.mkf" \
  detlist="launch,-14,-34" \
  outfile="${segID}/ni${segID}.rmf" \
  clobber=yes

nibackgen3C50 rootdir="." \
              obsid=${segID} \
              ufafile=${segID}/xti/event_cl/ni${segID}_0mpu7_ufa.evt \
              clfile=${segID}/xti/event_cl/ni${segID}_0mpu7_cl.evt \
              bkgidxdir="CALDB" \
              bkglibdir="CALDB" \
              gainepoch="AUTO" \
              fpmofflist="14,34" \
              bkgspec=${segID}/ni${segID}_bkg \
              totspec=${segID}/ni${segID}_tot \
              clobber=yes

grppha <<EOF
${segID}/ni${segID}_tot.pi
${segID}/ni${segID}_grp.pha
chkey BACKFILE ${segID}/ni${segID}_bkg.pi
chkey RESPFILE ${segID}/ni${segID}.rmf
chkey ANCRFILE ${segID}/ni${segID}.arf
group min ${gpmin}
exit
EOF

xspec <<EOF
data ${segID}/ni${segID}_grp.pha
ignore ${ign}
model tbabs*ztbabs*powerlaw
0.538 -1
1.29
0.151 -1
1.8
1.0
fit
error 2 4
cpd /xs
setplot energy
setplot background
plot ldata delchi
quit
EOF