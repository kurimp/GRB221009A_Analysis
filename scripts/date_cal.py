import astropy.units as u
from astropy.time import Time
import sys

if len(sys.argv) == 1:
  time_elapsed_from_trigger = 0
else:
  time_elapsed_from_trigger = sys.argv[1]

MJDREF = Time(59861.55346065, format='mjd')
time_elapsed_from_trigger = u.Quantity(time_elapsed_from_trigger, u.s)

time_abs = MJDREF + time_elapsed_from_trigger

print(time_abs.iso)