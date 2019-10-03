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
import colorful as cf

from tools.configs import LONG_LINE

DISABLE_COLORS = os.environ.get('DISABLE_COLORS', None)

cf.use_style('solarized')

PALETTE = {
    'success': '#00c853',
    'info': '#1976d2',
    'error': '#d50000'
}


def arguments_list_string(args, title=None, type='info'):
    s = f'\n{LONG_LINE}\n' if DISABLE_COLORS else cf.blue(f'\n{LONG_LINE}\n')
    if title:
        if DISABLE_COLORS:
            s += f'{title}\n'
        else:
            with cf.with_palette(PALETTE) as c:
                if type == 'error':
                    s += f'{c.bold_error(title)}\n'
                elif type == 'success':
                    s += f'{c.bold_success(title)}\n'
                else:
                    s += f'{c.bold_info(title)}\n'
    for k in args:
        s += f'{k}: ' if DISABLE_COLORS else f'{cf.bold_violet(k)}: '
        s += f'{args[k]}\n'
    s += f'{LONG_LINE}\n' if DISABLE_COLORS else cf.blue(f'{LONG_LINE}\n')
    return s
