#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
import re
import docker
import logging
from flask import Blueprint, request, send_file, after_this_request

from core.logs import Logs
from tools.config import LOG_TYPES

from web.helper import construct_ok_response, construct_err_response, \
    construct_key_error_response, login_required

logger = logging.getLogger(__name__)

logs = Logs()
web_logs = Blueprint('logs', __name__)


@web_logs.route('/logs', methods=['GET'])
@login_required
def logs_info():
    logger.debug(request)
    res = logs.get_all_info()
    return construct_ok_response(res)


@web_logs.route('/container-logs', methods=['GET'])
@login_required
def get_container_logs():
    logger.debug(request)
    try:
        container_name = request.args['container_name']
    except KeyError as e:
        return construct_key_error_response(e.args)
    lines = request.args.get('lines')
    if lines: lines = int(lines)
    try:
        container_logs = logs.get_container_logs(container_name, lines)
        return construct_ok_response(container_logs.decode("utf-8"))
    except docker.errors.NotFound:
        return construct_err_response(400, [f'No such container: {container_name}'])


@web_logs.route('/download-log-file', methods=['GET'])
@login_required
def download_log_file():
    logger.debug(request)

    filename = request.args.get('filename')
    type = request.args.get('type')
    schain_name = request.args.get('schain_name')

    if type not in LOG_TYPES:
        return construct_err_response(400)

    log_filepath, full_filename = logs.get_filepath(type, filename, schain_name)

    if not os.path.isfile(log_filepath):
        return construct_err_response(400, ['File not exist'])

    return send_file(log_filepath,
                     attachment_filename=full_filename,
                     as_attachment=True)


@web_logs.route('/logs/dump', methods=['GET'])
@login_required
def dump():
    @after_this_request
    def cleanup_logs_dump(response): # todo: move it to utils
        d = response.headers['Content-Disposition']
        fname_q = re.findall("filename=(.+)", d)[0]
        fname = fname_q.replace('"', '')
        folder_name = fname.replace('.tar.gz', '')
        dump_path = os.path.join('/tmp', folder_name)
        shutil.rmtree(dump_path)
        return response

    logger.debug(request)
    container_name = request.args.get('container_name')
    archive_path, archive_name = logs.get_containers_logs(container_name)
    if not archive_path or not os.path.isfile(archive_path):
        return construct_err_response(400, ['File not exist'])
    return send_file(archive_path,
                     attachment_filename=archive_name,
                     as_attachment=True)