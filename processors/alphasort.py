"""
AlphaSort
"""

import string
import os

from lxml import etree

import gelconfig
from lex.gel.fileiterator import FileIterator

file_size = gelconfig.FILE_SIZE_FINAL
xsl_uri = gelconfig.XSL_MAIN_URI
xslpi = etree.PI('xml-stylesheet', 'type="text/xsl" href="%s"' % xsl_uri)
alphabet = list(string.ascii_lowercase)


class AlphaSort(object):

    def __init__(self, in_dir, out_dir):
        self.iterator = FileIterator(in_dir=in_dir,
                                     out_dir=None,
                                     verbosity='low')
        self.out_dir = out_dir
        self.streams = {}

    def process(self):
        self.initialize()
        for filecontent in self.iterator.iterate():
            for entry in filecontent.entries:
                sortcode = entry.attribute('sort') or 'zzz'
                initial = sortcode[0]
                self.streams[initial].add_to_buffer(entry.node)
        # finish off writing anything left in the buffer
        for initial in alphabet:
            self.streams[initial].write()
        for initial in alphabet:
            print('sorting %s...' % initial)
            self.streams[initial].sort_in_place()

    def initialize(self):
        self.streams = {}
        for initial in alphabet:
            self.streams[initial] = LetterSet(initial, self.out_dir)
            self.streams[initial].purge_directory()


class LetterSet(object):

    def __init__(self, letter, out_dir):
        self.letter = letter
        self.filecount = 0
        self.out_dir = os.path.join(out_dir, letter)
        self.clear_buffer()

    def clear_buffer(self):
        self.doc = etree.Element('entries')
        self.doc.addprevious(xslpi)

    def add_to_buffer(self, node):
        self.doc.append(node)
        if self.size >= file_size:
            self.write()

    @property
    def size(self):
        return len(self.doc)

    @property
    def out_file(self):
        self.filecount += 1
        return os.path.join(self.out_dir, '%04d.xml' % (self.filecount,))

    def write(self):
        if self.size:
            with open(self.out_file, 'w') as filehandle:
                filehandle.write(etree.tostring(self.doc.getroottree(),
                                                pretty_print=True,
                                                encoding='unicode'))
        self.clear_buffer()

    def purge_directory(self):
        if not os.path.isdir(self.out_dir):
            os.mkdir(self.out_dir)
        for f in [f for f in os.listdir(self.out_dir)\
                  if os.path.splitext(f)[1] == '.xml']:
            os.unlink(os.path.join(self.out_dir, f))

    def sort_in_place(self):
        self.filecount = 0
        iterator = FileIterator(in_dir=self.out_dir,
                                out_dir=None,
                                verbosity=None)
        entries = []
        for filecontent in iterator.iterate():
            for entry in filecontent.entries:
                sortcode = entry.attribute('sort') or 'zzz'
                entries.append((sortcode, entry.tostring()))
        self.purge_directory()
        self.clear_buffer()
        entries.sort(key=lambda e: e[0])
        for entry in entries:
            node = etree.fromstring(entry[1])
            self.add_to_buffer(node)
        self.write()
