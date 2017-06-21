# -*- coding: utf-8 -*-
#
# Plugin configuration

DIVI_HOST = 'https://divi.io'
CONFIG_NAME = 'divi'

try:
    from local_config import *
except ImportError:
    pass
