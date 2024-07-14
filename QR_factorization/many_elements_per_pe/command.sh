#!/usr/bin/env bash
set -e

if [ -z $1 ] || [ -z $2 ] || [ -z $3 ] || [ -z $4 ]
then
  echo "usage: ./command.sh [N] [M] [grid width] [grid height]"
  exit 1
fi

if [ $(($1 % $3)) != 0 ] || [ $(($2 % $4)) != 0 ]
then
  echo "N must be divisible by grid width and M must be divisible by grid height"
  exit 1
fi

if [ $(($1 / $3)) != $(($2 / $4)) ]
then
  echo "[N]/[grid width] must be equal to [M]/[grid height]"
  exit 1
fi

cslc --arch=wse2 layout.csl --fabric-dims=`expr $3 + 7`,`expr $4 + 2` --fabric-offsets=4,1 --params=M:$2,N:$1,grid_width:$3,grid_height:$4 -o out --memcpy --channels=1
cs_python run.py --name out
tail -2 sim.log