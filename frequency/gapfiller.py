"""
GapFiller
"""

import os
import string
from time import sleep
import re

from lex import lexconfig
from stringtools import lexical_sort
from frequency.frequencyiterator import FrequencyIterator
from lex.gbn.googlebooksapi import GoogleBooksApi

GBN_DIR = lexconfig.NGRAMS_TABLES_DIR
SLEEPTIME = 2  # delay (in seconds) between calls to Google Ngrams site


def find_gaps(in_dir):
    """
    Check for lemmas which don't have any ngram data, and try to find these
    ngrams from the Google Ngram Viewer site
    """
    freq_iterator = FrequencyIterator(inDir=in_dir,
                                      outDir=None,
                                      message='Checking for gaps')

    # Iterate through each entry in the frequency build files
    gaps = []
    for entry in freq_iterator.iterate():
        if (not entry.tagged_ngrams and
                not "'s-" in entry.form and
                is_4gram_or_5gram(entry.form)):
                #is_initialled_name(entry.form)):
            gaps.append(entry.form)

    outfile = os.path.join(GBN_DIR, '4', 'tmp', next_filename(GBN_DIR))
    with open(outfile, 'w') as filehandle:
        for g in gaps:
            filehandle.write(g + '\n')


def fill_gaps(**kwargs):
    """
    Try To find ngrams for missing lemmas by scraping data from
    the Google Ngram Viewer site
    """
    letters = kwargs.get('letters', string.ascii_lowercase)

    # Load list of gaps from file
    infile = os.path.join(GBN_DIR, '4', 'tmp', filename(GBN_DIR))
    with open(infile, 'r') as filehandle:
        gaps = [l.strip() for l in filehandle.readlines()]
    gaps = [g for g in gaps if lexical_sort(g)
            and lexical_sort(g)[0] in letters]

    results = {letter: [] for letter in letters}
    gba = GoogleBooksApi(start=1750, end=2008)

    # We cluster ngrams into sets of five, which will be dealt with in
    #  a single request - cutting down the number of requests
    clusters = _cluster(gaps, 5)

    for ngram_set in clusters:
        print(ngram_set[0])
        for result in gba.get_ngram_data(queries=ngram_set):
            results[result.initial()].append(result)
            #print(result.tostring())
        sleep(SLEEPTIME)

    for letter in results:
        subdir = os.path.join(GBN_DIR, '4', letter)
        if not os.path.exists(subdir):
            os.mkdir(subdir)
        with open(os.path.join(subdir, filename(GBN_DIR)), 'w') as filehandle:
            for r in results[letter]:
                filehandle.write(r.tostring() + '\n')


def is_4gram_or_5gram(form):
    form2 = form
    for before, after in (("'-", '-'), ("' ", " ' "), ('-', ' - '),
                          ("'s", " 's"), ("' ", " ' "), ('  ', ' ')):
        form2 = form2.replace(before, after)
    tokens = form2.strip(" '").split()
    if len(tokens) in (4, 5) or form[-1] == '!':
        return True
    else:
        return False


def is_initialled_name(form):
    if (re.search(r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$', form) or
            re.search(r'^[A-Z]\. [A-Z]\. [A-Z][a-z]+$', form) or
            re.search(r'^[A-Z]\. [A-Z][a-z]+ [A-Z][a-z]+$', form)):
        return True
    else:
        return False


def is_proper_name(form):
    return len(form) > 2 and form.istitle()


def _cluster(ngrams, cluster_size):
    return [ngrams[i:i+cluster_size] for i in
            range(0, len(ngrams), cluster_size)]


def filename(dir):
    files = sorted([f for f in os.listdir(os.path.join(dir, '4', 'tmp'))
                    if f.endswith('.txt')])
    return files[-1]


def next_filename(dir):
    files = sorted([f for f in os.listdir(os.path.join(dir, '4', 'tmp'))
                    if f.endswith('.txt')])
    if not files:
        num = 1
    else:
        num = int(files[-1].split('.')[0]) + 1
    return '%04d.txt' % num
