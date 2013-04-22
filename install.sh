#!/usr/bin/env bash

echo "Modifying python path..."
echo PYTHONPATH=$PYTHONPATH:$( cd $( dirname $0 ) : pwd ) >> ~/.pam_environment

