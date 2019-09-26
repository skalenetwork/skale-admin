import os
from tools.config import PROJECT_DIR

LVM_SCRIPT_NAME = 'lvm.sh'
LVM_SCRIPT_PATH = os.path.join(PROJECT_DIR, 'server', 'core', 'lvm', LVM_SCRIPT_NAME)

VOL_GROUP_NAME = 'SkaleLVMVolGroup'
#VOL_GROUP_NAME = 'LVMVolGroup'