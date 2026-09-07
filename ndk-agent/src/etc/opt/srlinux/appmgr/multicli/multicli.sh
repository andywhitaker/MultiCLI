#!/bin/bash

_term (){
    echo "Caught signal SIGTERM !! "
    # when SIGTERM is caught: kill the child process
    kill -TERM "$child" 2>/dev/null
}

# associate a handler with signal SIGTERM
trap _term SIGTERM

#sudo su

# set local variables
virtual_env="/opt/srlinux/python/virtual-env/bin/activate"
main_module="/etc/opt/srlinux/appmgr/multicli/multicli.py"

# start python virtual environment
source "${virtual_env}"

# update PYTHONPATH variable with the agent directory and the SR Linux gRPC
PYBASE="/opt/srlinux/python/virtual-env/lib"

if [ -d "${PYBASE}/python3.13" ]; then
    PYVER="python3.13" # SRL 26.X
elif [ -d "${PYBASE}/python3.11" ]; then
    PYVER="python3.11" # SRL 25.X
fi

export PYTHONPATH="$PYTHONPATH:/etc/opt/srlinux/helper:/etc/opt/srlinux/appmgr/multicli:/opt/srlinux/bin:/usr/lib/${PYVER}/dist-packages/sdk_protos:/usr/lib/${PYVER}/dist-packages"

# start the agent in the background (as a child process)
python3 ${main_module} &

# save its process id
child=$!

# wait for the child process to finish
wait "$child"
