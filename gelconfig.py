"""
gelconfig - Configuration for the GEL build process
"""

import os

from lex import lexconfig


#=====================================================================
# Pipeline (list of functions to be executed)
#=====================================================================

PIPELINE = (
    ('distilOdo', 0),
    ('generateMorphologyHub', 0),
    ('updateLinkTables', 0),
    ('indexOedSize', 0),
    ('generateBase', 0),
    ('mergeEntryPairs', 0),
    ('addInflections', 0),
    ('addOdoContent', 0),
    ('cleanAttributes', 0),
    ('frequencyListLemmas', 0),
    ('frequencyCompileNgrams', 0),
    ('frequencyCheckGaps', 0),
    ('frequencyRecompilePredictors', 0),
    ('frequencyComputeScores', 0),
    ('insertFrequency', 1),
    ('alphabetizeOutput', 1),
    ('indexOutput', 1),
)


#=====================================================================
# Filepaths
#=====================================================================

BUILD_DIR = os.path.join(lexconfig.GEL_DIR, 'build')
FINAL_DIR = os.path.join(lexconfig.GEL_DIR, 'globalEnglishLexicon')
FINAL_DATA_DIR = os.path.join(FINAL_DIR, 'data')
FINAL_ANCILLARY_DIR = os.path.join(FINAL_DIR, 'ancillary')

RESOURCES_DIR = os.path.join(lexconfig.GEL_DIR, 'resources')
FREQUENCY_BUILD_DIR = os.path.join(BUILD_DIR, 'frequency_build')
WEIGHTED_SIZE_DIR = os.path.join(RESOURCES_DIR, 'weighted_size_index')


#=====================================================================
# Base build parameters
#=====================================================================

# Number of entries per output file.
FILE_SIZE_BUILD = 1000
FILE_SIZE_FINAL = 500

# Number of digits used in IDs.
ID_LENGTH = 9

# Maximum number of characters in definitions. Longer definitions
#   will be truncated.
DEFINITION_LENGTH = 100

# Minimum number of quotations a lemma must have to be included.
#  Set to '0' to include all lemmas, even unevidenced ones.
MINIMUM_NUM_QUOTATIONS = 1


#=====================================================================
# Date range
#=====================================================================

DATE_MINIMUM = 1200
DATE_MINIMUM_PROXY = 1100
DATE_MAXIMUM = 2050

# Dates used for undated/unevidenced OED lemmas.
DATE_SPECULATIVE_START = 1800
DATE_SPECULATIVE_END = 1899

# Start date used for ODE/NOAD-only lemmas (if the etymology doesn't specify).
DATE_ODO_START = 1980


#=====================================================================
# Date granularity
#=====================================================================

DATE_GRANULARITY_ME = 100  # Middle English
DATE_GRANULARITY_EMODE = 50  # Early Modern English
DATE_GRANULARITY_MODE = 50  # Modern English


#=====================================================================
# Variants
#=====================================================================

# If a lemma is obsolete before this date, a US spelling variant
#  will not be computed.
VAR_US_MINIMUM = 1900

# (NB most settings relating to variants are in
#  lex.oed.variants.variantsconfig, and get imported by
#  lex.oed.variants.variantscomputer)


#=====================================================================
# Inflections
#=====================================================================

# Plurals will not be *computed* for words ending with the following.
#  (Regex syntax is supported, e.g. character classes.)
UNPLURALIZED = 'ism|ization|phony|hood|dom|ship|ness|itis|genesis|philia|music'


#=====================================================================
# Frequency
#=====================================================================

FREQUENCY_AVERAGES = os.path.join(FREQUENCY_BUILD_DIR, 'averages.xml')
FREQUENCY_PREDICTION_DIR = os.path.join(RESOURCES_DIR, 'frequency_prediction')
OEC_LEMPOS_PROBABILITIES = os.path.join(RESOURCES_DIR, 'corpus',
                                        'oec_lempos_probabilities.txt')
OEC_POS_PROBABILITIES = os.path.join(RESOURCES_DIR, 'corpus',
                                     'oec_pos_probabilities.txt')
BNC_PROBABILITIES = os.path.join(RESOURCES_DIR, 'corpus',
                                 'bnc_probabilities.txt')

FREQUENCY_PERIODS = (
    ('1750-59', (1750, 1759)),
    ('1760-69', (1760, 1769)),
    ('1770-79', (1770, 1779)),
    ('1780-89', (1780, 1789)),
    ('1790-99', (1790, 1799)),
    ('1800-09', (1800, 1809)),
    ('1810-19', (1810, 1819)),
    ('1820-29', (1820, 1829)),
    ('1830-39', (1830, 1839)),
    ('1840-49', (1840, 1849)),
    ('1850-59', (1850, 1859)),
    ('1860-69', (1860, 1869)),
    ('1870-69', (1870, 1879)),
    ('1880-89', (1880, 1889)),
    ('1890-99', (1890, 1899)),
    ('1900-09', (1900, 1909)),
    ('1910-19', (1910, 1919)),
    ('1920-29', (1920, 1929)),
    ('1930-39', (1930, 1939)),
    ('1940-49', (1940, 1949)),
    ('1950-59', (1950, 1959)),
    ('1960-69', (1960, 1969)),
    ('1970-79', (1970, 1979)),
    ('1980-89', (1980, 1989)),
    ('1990-99', (1990, 1999)),
    ('2000-', (2000, 2008)),
    ('modern', (1970, 2008)),
)


#=====================================================================
# XSL links (for final XML documents)
#=====================================================================

# Relative links from content files to XSL stylesheets.
XSL_MAIN_URI = '../../chrome/xsl/lexicon.xsl'
XSL_INDEX_URI = '../../chrome/xsl/index.xsl'
