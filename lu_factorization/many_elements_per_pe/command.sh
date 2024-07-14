#!/usr/bin/env bash

if [ -z $1 ] || [ -z $2 ]
then
  echo "usage: ./command.sh [matrix side size (n)] [grid side size]"
  exit 1
fi

if [ $(($1 % $2)) != 0 ]
then
  echo "matrix side size must be divisible by grid side size"
  exit 1
fi

set -e

cslc --arch=wse2 layout.csl --fabric-dims=`expr $2 + 7`,`expr $2 + 2` --fabric-offsets=4,1 --params=M:$1,grid_size:$2 -o out --memcpy --channels=1
cs_python run.py --name out
tail -2 sim.log