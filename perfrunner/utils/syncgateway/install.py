import sys
import os
from perfrunner.utils.syncgateway.ansible_runner import AnsibleRunner
from logger import logger


def main():

    _uninstall = False
    for i, item in enumerate(sys.argv):
        if item == "-build":
            _build = sys.argv[i + 1]
        elif item == "-cluster":
            _cluster_path = sys.argv[i + 1]
        elif item == "-config":
            _config_path = sys.argv[i + 1]
        elif item == "--uninstall":
            _uninstall = True

    v, b = _build.split("-")

    if v == "2.0.0":
        base_url = "http://latestbuilds.service.couchbase.com/builds/releases/mobile/couchbase-sync-gateway/2.0.0"
    else:
        base_url = "http://latestbuilds.service.couchbase.com/builds/latestbuilds/sync_gateway/{}/{}".format(v, b)
    sg_package_name = "couchbase-sync-gateway-enterprise_{}_x86_64.rpm".format(_build)
    accel_package_name = "couchbase-sg-accel-enterprise_{}_x86_64.rpm".format(_build)

    _config_full_path = os.path.abspath(_config_path)

    playbook_vars = dict()
    playbook_vars["sync_gateway_config_filepath"] = _config_full_path
    playbook_vars["couchbase_sync_gateway_package_base_url"] = base_url
    playbook_vars["couchbase_sync_gateway_package"] = sg_package_name
    playbook_vars["couchbase_sg_accel_package"] = accel_package_name

    if _uninstall:
        playbook = "remove-previous-installs.yml"
    else:
        playbook = "install-sync-gateway-package.yml"
    ansible_runner = AnsibleRunner(_cluster_path)

    status = ansible_runner.run_ansible_playbook(playbook, extra_vars=playbook_vars)
    if status != 0:
        logger.info("Failed to install sync_gateway package")
        sys.exit(1)


if __name__ == '__main__':
    main()


# env/bin/sg_install -build 1.5.0-582 -cluster perfrunner/utils/syncgateway/clusters/hebe_4node.cluster -config perfrunner/utils/syncgateway/configs/hebe_xattr_sync.config
