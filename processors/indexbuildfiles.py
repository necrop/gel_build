"""
index_build_files
"""

import csv

from lex.gel.fileiterator import FileIterator


def index_build_files(dir, out_file):
    iterator = FileIterator(in_dir=dir, out_dir=None, verbosity=None)

    index = []
    for filecontent in iterator.iterate():
        headwords = []
        for entry in filecontent.entries:
            headwords.append(entry.lemma)
        index.append((iterator.file_number(),
                      headwords[0],
                      headwords[-1]))

    with open(out_file, 'w') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerows(index)
