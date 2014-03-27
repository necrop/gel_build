"""
idgenerator
"""

import random

import gelconfig

FORMATTER = '%0' + str(gelconfig.ID_LENGTH) + 'd'
count = int(random.uniform(100000, 200000))


def next_id():
    """
    Return consecutive IDs
    """
    global count
    count += 1
    return FORMATTER % count

