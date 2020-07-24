docker_lvmpy_install () {
    if [[ ! -d docker-lvmpy ]]; then
        git clone "https://github.com/skalenetwork/docker-lvmpy.git"
    fi
    cd docker-lvmpy
    echo "Checkouting to $DOCKER_LVMPY_STREAM ..."
    git checkout $DOCKER_LVMPY_STREAM
    echo "Running install.sh script ..."
    if [ -z ${BLOCK_DEVICE} ]; then
        echo 'Creating loopback block device'
        dd if=/dev/zero of=loopbackfile.img bs=400M count=10
        losetup -fP loopbackfile.img
        losetup -a
        echo 'Block device created from file'
        BLOCK_DEVICE="$(losetup --list -a | grep loopbackfile.img |  awk '{print $1}')"
        export BLOCK_DEVICE
    fi
    echo 'Installing docker-lvmpy'
    VOLUME_GROUP=schains PHYSICAL_VOLUME=$BLOCK_DEVICE scripts/install.sh
    cd -
}

docker_lvmpy_finalize () {
    echo "Disable docker-lvmpy service"
    systemctl disable docker-lvmpy
    if [ "$(sudo vgs | grep schain)" ]; then
        echo "Removing all volumes from schain volume group"
        lvremove schains --yes
        echo "Removing volume group schain"
        vgremove schains
        echo "Cleaning up $BLOCK_DEVICE"
        pvremove $BLOCK_DEVICE
        echo "Unmount $BLOCK_DEVICE"
        umount $BLOCK_DEVICE
    fi;
    BLOCK_DEVICE="$(losetup --list -a | grep loopbackfile.img |  awk '{print $1}')"
    if [ ! -z "${BLOCK_DEVICE}" ]; then
        echo "Removing $BLOCK_DEVICE"
        losetup -d $BLOCK_DEVICE
        echo 'Removing loopbackfile.img'
        sudo rm -f docker-lvmpy/loopbackfile.img
    fi
}

set -e
source $VIRTUAL_ENV/bin/activate

docker_lvmpy_install

export SKALE_DIR_HOST=$PWD/tests/skale-data
export RUNNING_ON_HOST=True
export PYTHONPATH=${PYTHONPATH}:.
export ENV=dev
export SGX_CERTIFICATES_FOLDER=$PWD/tests/dkg_test/
export SGX_SERVER_URL=https://localhost:1026
export ENDPOINT=http://localhost:8545
export IMA_ENDPOINT=http://localhost:1000
export DB_USER=user
export DB_PASSWORD=pass
export DB_PORT=3307
export FLASK_APP_HOST=0.0.0.0
export FLASK_APP_PORT=3008
export FLASK_DEBUG_MODE=True
export TM_URL=http://localhost:3009
export TG_API_KEY=123
export SCHAIN_TYPE=test4

rm -rf $PWD/tests/dkg_test/sgx.*
docker rm -f node1 node2 node3 node4 || true
docker volume rm node1 node2 node3 node4 || true

bash scripts/run_sgx_simulator.sh

python tests/prepare_data.py

py.test tests/rotation_test/five_nodes/new_test.py

docker_lvmpy_finalize