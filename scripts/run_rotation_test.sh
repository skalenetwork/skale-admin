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

docker_lvmpy_install