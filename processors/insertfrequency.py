"""
InsertFrequency
"""

from lxml import etree

from lex.gel.fileiterator import FileIterator
from frequency.frequencymemo import FrequencyMemo
from lex.frequencytable import FrequencyTable, sum_frequency_tables


def insert_frequency(in_dir, out_dir, freq_dir):
    """
    Find frequency values in the frequency_build data, and inserts
    them in the GEL data.
    """
    iterator = FileIterator(in_dir=in_dir, out_dir=out_dir, verbosity='low')
    frequency_finder = FrequencyMemo(freq_dir)

    for filecontent in iterator.iterate():
        for entry in filecontent.entries:
            for wordclass_set in entry.wordclass_sets():
                etree.strip_attributes(wordclass_set.node, 'size')

                tables = {}
                for type in wordclass_set.types():
                    frequencies = frequency_finder.find_frequencies(type.id)
                    if frequencies:
                        tables[type.id] = FrequencyTable(data=frequencies)
                    else:
                        tables[type.id] = None

                for type in wordclass_set.types():
                    if tables[type.id]:
                        type.node.append(tables[type.id].to_xml())

                non_null_tables = [table for table in tables.values() if table]
                if non_null_tables:
                    wcs_table = sum_frequency_tables(non_null_tables)
                    wordclass_set.node.append(wcs_table.to_xml())
