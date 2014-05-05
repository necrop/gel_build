"""
FrequencyIterator
"""

import string
import os

from lxml import etree

from frequency.frequencyentry import FrequencyEntry

parser = etree.XMLParser(remove_blank_text=True)
alphabet = list(string.ascii_lowercase)


class FrequencyIterator(object):

    """
    Iterate through each entry in the build files for GEL frequency,
    yielding each entry in turn.

    If an output directory is supplied (as the outDir keyword argument),
    each input file is written out to the output directory.
    """

    def __init__(self, **kwargs):
        self.in_dir = kwargs.get('in_dir') or kwargs.get('inDir')
        self.out_dir = kwargs.get('out_dir') or kwargs.get('outDir')
        self.letters = kwargs.get('letters')
        self.verbosity = kwargs.get('verbosity')
        self.message = kwargs.get('message')
        if not self.message and self.verbosity:
            self.message = 'Processing frequency data'
        self.subdir = None

    def iterate(self):
        for letter in alphabet:
            if not self.letters or letter in self.letters:
                if self.message:
                    print('%s: %s...' % (self.message, letter,))
                if self.out_dir:
                    self.subdir = os.path.join(self.out_dir, letter)
                    self.clear_dir()

                files = [os.path.join(self.in_dir, letter, f) for f in
                         os.listdir(os.path.join(self.in_dir, letter))
                         if f.endswith('.xml')]

                for filepath in sorted(files):
                    doc = etree.parse(filepath, parser)
                    for lem_node in doc.findall('lemma'):
                        entry = FrequencyEntry(lem_node)
                        yield entry
                    self.print_output(filepath, doc)

    def print_output(self, filepath, doc):
        if self.out_dir:
            basename = os.path.basename(filepath)
            with open(os.path.join(self.subdir, basename), 'w') as filehandle:
                filehandle.write(etree.tounicode(doc, pretty_print=True))

    def clear_dir(self):
        if not os.path.isdir(self.subdir):
            os.mkdir(self.subdir)
        for f in os.listdir(self.subdir):
            os.unlink(os.path.join(self.subdir, f))
