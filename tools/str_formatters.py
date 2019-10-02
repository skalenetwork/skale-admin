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
