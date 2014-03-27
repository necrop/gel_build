"""
BuildIndex
"""

import string
import os
from collections import namedtuple

from lxml import etree

import gelconfig
from lex.gel.fileiterator import FileIterator

alphabet = list(string.ascii_lowercase)
xsl_uri = gelconfig.XSL_INDEX_URI
xslpi = etree.PI('xml-stylesheet', 'type="text/xsl" href="%s"' % xsl_uri)

FileData = namedtuple('FileData', ['path', 'name', 'num_entries',
                                   'first_entry', 'last_entry',
                                   'num_types', 'num_distinct_types'])


class BuildIndex(object):

    def __init__(self, in_dir, out_dir):
        self.in_dir = in_dir
        self.out_dir = out_dir
        self.data = {}
        self.stats = {}

    def process(self):
        self.compile_data()
        self.write()

    def compile_data(self):
        self.data = {}
        for letter in alphabet:
            print('Compiling index for %s...' % letter)
            self.data[letter] = []
            sub_dir = os.path.join(self.in_dir, letter)
            iterator = FileIterator(in_dir=sub_dir,
                                    out_dir=None,
                                    verbosity=None)
            for filecontent in iterator.iterate():
                filedata = _filedata_factory(iterator.in_file,
                                             filecontent.entries)
                self.data[letter].append(filedata)

        self.stats = {}
        for letter in alphabet:
            self.stats[letter] = {'entries': 0,
                                  'types': 0,
                                  'distinct_types': 0,
                                  'files': 0}
            for filedata in self.data[letter]:
                self.stats[letter]['files'] += 1
                self.stats[letter]['entries'] += filedata.num_entries
                self.stats[letter]['types'] += filedata.num_types
                self.stats[letter]['distinct_types'] += filedata.num_distinct_types
        self.stats['total'] = {'entries': 0,
                               'types': 0,
                               'files': 0,
                               'distinct_types': 0}
        for letter in alphabet:
            for z in ('entries', 'types', 'distinct_types', 'files'):
                self.stats['total'][z] += self.stats[letter][z]

    def write(self):
        doc = etree.Element('letters')
        doc.addprevious(xslpi)

        #total_nodes = etree.SubElement(doc, 'total',
        #              files=str(self.stats['total']['files']),
        #              entries=str(self.stats['total']['entries']),
        #              types=str(self.stats['total']['types']),
        #              distinctTypes=str(self.stats['total']['distinct_types']))

        for letter in alphabet:
            letter_node = etree.SubElement(doc, 'letterSet',
                                           letter=letter,
                                           files=str(self.stats[letter]['files']),
                                           entries=str(self.stats[letter]['entries']),
                                           types=str(self.stats[letter]['types']),
                                           distinctTypes=str(self.stats[letter]['distinct_types']))
            for filedata in self.data[letter]:
                fnode = etree.SubElement(letter_node, 'file',
                                         name=filedata.name,
                                         letter=letter,
                                         entries=str(filedata.num_entries))
                t1 = etree.SubElement(fnode, 'first')
                t1.text = filedata.first_entry
                t2 = etree.SubElement(fnode, 'last')
                t2.text = filedata.last_entry

        with open(os.path.join(self.out_dir, 'index.xml'), 'w') as filehandle:
            filehandle.write(etree.tostring(doc.getroottree(),
                                            pretty_print=True,
                                            encoding='unicode'))


def _filedata_factory(path, entries):
    all_types = []
    for entry in entries:
        for type in entry.types():
            all_types.append(type.form)
    distinct_types = set(all_types)

    return FileData(
        path,
        os.path.basename(path).replace('.xml', ''),
        len(entries),
        entries[0].lemma,
        entries[-1].lemma,
        len(all_types),
        len(distinct_types),
    )
