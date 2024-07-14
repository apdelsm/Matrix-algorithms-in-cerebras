#!/usr/bin/env bash
set -e

if [[ -z $1 ]]
then
  M=15
else
  M=$1
fi

if [[ -z $2 ]]
then
  N=15
else
  N=$2
fi

if [[ M -lt N ]]
then
  echo "M must be great or equal than N"
  exit 1
fi



cslc --arch=wse2 layout.csl --fabric-dims=`expr $N + 7`,`expr $M + 2` --fabric-offsets=4,1 --params=M:$M,N:$N -o out --memcpy --channels=1
cs_python run.py --name out
tail -2 sim.log