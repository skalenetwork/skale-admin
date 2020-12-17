#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
import re
import logging
from flask import Blueprint, request, send_file, after_this_request

from core.logs import Logs
from web.helper import construct_err_response, get_api_url

logger = logging.getLogger(__name__)

logs = Logs()
BLUEPRINT_NAME = 'logs'
web_logs = Blueprint(BLUEPRINT_NAME, __name__)


@web_logs.route(get_api_url(BLUEPRINT_NAME, 'dump'), methods=['GET'])
def dump():
    @after_this_request
    def cleanup_logs_dump(response):  # todo: move it to utils
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
        return construct_err_response(msg='File not exist')
    return send_file(archive_path,
                     attachment_filename=archive_name,
                     as_attachment=True)
