#!/usr/bin/env bash

if [[ -z $1 ]]
then
  N=15
else
  N=$1
fi

set -e

cslc --arch=wse2 layout.csl --fabric-dims=`expr $N + 7`,`expr $N + 2` --fabric-offsets=4,1 --params=M:$N,N:$N -o out --memcpy --channels=1
cs_python run.py --name out
tail -2 sim.log