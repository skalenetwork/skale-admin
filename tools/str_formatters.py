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

from typing import Any, Dict, Literal, Optional

import colorful as cf

from tools.settings import get_settings

cf.use_style('solarized')
PALETTE = {
    'success': '#00c853',
    'info': '#1976d2',
    'error': '#d50000',
    'warning': '#ff6f00',
    'primary': '#6200ea',
    'secondary': '#00838f',
    'lime': '#cddc39',
    'pink': '#e91e63',
    'light': '#D7AFFF',
    'cyan': '#00bcd4',
}


def arguments_list_string(
    args: Dict[str, Any],
    title: Optional[str] = None,
    type: Literal[
        'info', 'success', 'error', 'warning', 'primary', 'secondary', 'lime', 'pink', 'light'
    ] = 'info',
) -> str:
    st = get_settings()
    if st.disable_colors:
        title_part = f'{title} - ' if title else ''
        args_part = ', '.join(f'{key}: {value}' for key, value in args.items())
        return f'{title_part}{{{args_part}}}'

    with cf.with_palette(PALETTE) as c:
        color_fn = getattr(c, f'bold_{type}')
        title_part = str(color_fn('> ' + title + ' - ')) if title else str(color_fn('> '))
        args_part = ', '.join(
            f'{str(c.bold_cyan(key))}: {str(c.light(value))}' for key, value in args.items()
        )
        return f'{title_part}{str(color_fn("{"))} {args_part} {str(color_fn("}"))}'
