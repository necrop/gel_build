"""
LinkTableUpdater
"""

import os

from lex import lexconfig
from lex.odo.linkmanager import LinkInferrer, LinkUpdater

LINKS_DIR = lexconfig.ODO_LINKS_DIR
ODO_SOURCE_FILE = os.path.join(LINKS_DIR, 'source', '%s_to_oedlatest_20120817.xml')
ODO_OUTPUT_FILE = os.path.join(LINKS_DIR, '%s_to_oed.xml')
OED_SOURCE_FILE = os.path.join(LINKS_DIR, 'source', 'oed_to_ode.xml')
OED_TO_ODE = os.path.join(LINKS_DIR, 'oed_to_ode.xml')
OED_TO_NOAD = os.path.join(LINKS_DIR, 'oed_to_noad.xml')


def update_tables():
    for dictname in ('ode', 'noad'):
        print('Updating link table for %s...' % dictname.upper())
        updater = LinkUpdater(
            dictName=dictname,
            odoIn=ODO_SOURCE_FILE % dictname,
            odoOut=ODO_OUTPUT_FILE % dictname,
        )
        updater.update_odo(validLinksOnly=True)

    print('Updating link table for OED -> ODE...')
    updater = LinkUpdater(
        dictName='ode',
        oedIn=OED_SOURCE_FILE,
        oedOut=OED_TO_ODE,
    )
    updater.update_oed(validLinksOnly=True)


def infer_noad():
    print('Inferring link table for OED -> NOAD...')
    inferrer = LinkInferrer(
        inFile=OED_TO_ODE,
        outFile=OED_TO_NOAD,
    )
    inferrer.infer()

