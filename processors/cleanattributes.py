"""
clean_attributes
"""

from lex.gel.fileiterator import FileIterator
from idgenerator import next_id

REMOVABLE = ('oedLexid', 'odoLexid', 'tag', 'oedId', 'parentId')


def clean_attributes(in_dir, out_dir):
    """
    Clean up GEL data by adding/removing/adjusting various attributes.

    - Add a unique ID to every entry, wordclass set, morphset, and type;
    - Add a sort code to every entry, morphset, and type;
    - Fuzz start and end dates (approximate to nearest 50 or 100 years);
    - Remove unnecessary attributes from entry tags.
    """

    iterator = FileIterator(in_dir=in_dir, out_dir=out_dir, verbosity='low')
    for filecontent in iterator.iterate():
        for entry in filecontent.entries:
            for att in REMOVABLE:
                if att in entry.node.attrib:
                    entry.node.attrib.pop(att)
            entry.node.set('id', next_id())
            entry.node.set('sort', entry.sort)

            for block in entry.wordclass_sets():
                block.node.set('id', next_id())
                block.fuzz_dates()
                for morphset in block.morphsets():
                    morphset.node.set('id', next_id())
                    morphset.node.set('sort', morphset.sort)
                    morphset.fuzz_dates()
                    for typeunit in morphset.types():
                        typeunit.node.set('id', next_id())
                        typeunit.node.set('sort', typeunit.sort)
