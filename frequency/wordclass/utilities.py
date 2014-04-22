"""
Utilities
"""


def wordclass_base(wordclass):
    if wordclass in ('NN', 'NNS', 'NP'):
        return 'NN'
    elif wordclass in ('VB', 'VBZ', 'VBG', 'VBD', 'VBN', 'MD'):
        return 'VB'
    elif wordclass in ('JJ', 'JJR', 'JJS'):
        return 'JJ'
    elif wordclass in ('RB', 'RBR', 'RBS'):
        return 'RB'
    else:
        return wordclass


def wordclass_group(wordclass):
    if wordclass_base(wordclass) in ('NN', 'VB', 'JJ'):
        return 'core'
    else:
        return 'other'


def adjust_to_unity(ratios):
    """
    Adjust a dictionary of ratios so that they sum to 1
    """
    total = sum(ratios.values())
    adjusted = dict()
    for wordclass, value in ratios.items():
        if total > 0:
            adjusted[wordclass] = (1.0 / total) * value
        else:
            adjusted[wordclass] = 1.0 / len(ratios)
    return adjusted


def wordclass_category(wordclass):
    """
    Used in compiling frequency regression data
    """
    if wordclass in ('MD',):
        category = 'VB'
    elif wordclass in ('NP',):
        category = 'NN'
    elif wordclass in ('IN', 'CC', 'DT', 'EX', 'PDT', 'PP', 'PP$', 'TO',
                'WDT', 'WP', 'WP$', 'WRB'):
        category = 'FUNCWD'
    elif wordclass in ('UH', 'POS', 'SYM', 'CD'):
        category = 'MISC'
    else:
        category = wordclass
    return category
