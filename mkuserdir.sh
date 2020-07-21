#!/bin/sh
for i in `seq 1 ${#}`
do
  user="$1"
  if [ ! -e $user ];then
    mkdir $user
    chown $user.$user $user
    chmod 755 $user
  fi
  shift
done

