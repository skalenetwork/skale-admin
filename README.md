# SKALE Admin

[![Build Status](https://travis-ci.com/skalenetwork/skale-admin.svg?token=tLesVRTSHvWZxoyqXdoA&branch=develop)](https://travis-ci.com/skalenetwork/skale-admin)

SKALE Admin is the container that manages all operations on the SKALE node.

Test build:

```bash
export BRANCH=$(git branch | grep -oP "^\*\s+\K\S+$")
export VERSION=$(bash scripts/calculate_version.sh)
bash scripts/build.sh 
```