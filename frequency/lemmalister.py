"""
LemmaLister - List all the lemmas and wordforms for which we'll be
compiling frequency data.
"""

import os
import string
from collections import defaultdict, namedtuple

from lxml import etree

from lex.gel.fileiterator import FileIterator

MINIMUM_END_DATE = 1800
FormData = namedtuple('FormData', ['form', 'sort', 'wordclass_id',
                                   'type_id', 'xrid', 'xnode', 'wordclass',
                                   'start', 'end', 'baseform'])


class LemmaLister(object):

    """
    List every type in GEL in alpha order, so that homographs are
    put together in sets, along with their vital statistics.
    """

    def __init__(self, in_dir, out_dir):
        self.in_dir = in_dir
        self.out_dir = out_dir

    def process(self):
        iterator = FileIterator(in_dir=self.in_dir,
                                out_dir=None,
                                verbosity='low')

        forms = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for filecontent in iterator.iterate():
            for entry in filecontent.entries:
                for wordclass_forms in _process_entry(entry):
                    for item in wordclass_forms:
                        initial = item.sort[0]
                        forms[initial][item.sort][item.form].append(item)

        for initial, sortcode_set in forms.items():
            self.subdir = os.path.join(self.out_dir, initial)
            self.clear_dir()
            self.filecount = 0
            self.initialize_doc()
            for sortcode, form_set in sorted(sortcode_set.items()):
                for form, items in sorted(form_set.items()):
                    entry = etree.Element('lemma', sort=sortcode)
                    form_node = etree.SubElement(entry, 'form')
                    form_node.text = form
                    lex_node = etree.Element('lex')
                    for item in items:
                        instance_node = etree.Element(
                            'instance',
                            wordclassId=item.wordclass_id,
                            typeId=item.type_id,
                            wordclass=item.wordclass,
                            start=str(item.start),
                            end=str(item.end),
                            base=item.baseform,
                            )
                        if item.xrid:
                            instance_node.set('xrid', item.xrid)
                        if item.xnode:
                            instance_node.set('xnode', item.xnode)
                        lex_node.append(instance_node)
                    entry.append(lex_node)
                    self.doc.append(entry)
                    if len(self.doc) > 10000:
                        self.writebuffer()
            self.writebuffer()

    def clear_dir(self):
        if not os.path.isdir(self.subdir):
            os.mkdir(self.subdir)
        for f in os.listdir(self.subdir):
            os.unlink(os.path.join(self.subdir, f))

    def writebuffer(self):
        xml_string = etree.tostring(self.doc,
                                    pretty_print=True,
                                    encoding='unicode')
        filename = self.next_filename()
        with open(filename, 'w') as filehandle:
            filehandle.write(xml_string)
        self.initialize_doc()

    def initialize_doc(self):
        self.doc = etree.Element('entries')

    def next_filename(self):
        self.filecount += 1
        return os.path.join(self.subdir, '%04d.xml' % (self.filecount,))


def _process_entry(entry):
    return [_process_wordclass(entry, wcs) for wcs in entry.wordclass_sets()]


def _process_wordclass(entry, wordclass_set):
    # Skip obsolete or near-obsolete stuff
    if (wordclass_set.date() and
            wordclass_set.date().is_marked_obsolete() and
            wordclass_set.date().end < 1900):
        return {}
    if (wordclass_set.date() and
            wordclass_set.date().end < MINIMUM_END_DATE):
        return {}

    oed_id, oed_xnode = wordclass_set.link(target='oed', asTuple=True)

    # Set of forms that should be omitted if encountered
    if wordclass_set.wordclass() == 'NP':
        omit = _np_handler(wordclass_set)
    else:
        omit = set()

    # Anything that matches or fuzzy-matches the form of the lemmas
    # (allowing for digraph adjustment) should be included
    permissible_forms = set([h.lexical_sort() for h in entry.lemmas()])
    digraph_adjusted = [f.replace('oe', 'e').replace('ae', 'e') for f in
                        permissible_forms]
    for wordform in digraph_adjusted:
        permissible_forms.add(wordform)

    forms = defaultdict(list)
    for i, morphset in enumerate(wordclass_set.morphsets()):
        if (morphset.date() and
                morphset.date().end and
                morphset.date().end < MINIMUM_END_DATE):
            continue
        if morphset.is_nonstandard():
            continue
        if (i > 0 and
                wordclass_set.wordclass != 'NP' and
                morphset.sort not in permissible_forms):
            continue

        for typeunit in morphset.types():
            if typeunit.sort and not typeunit.sort in omit:
                if not morphset.date():
                    start, end = (0, 0)
                else:
                    start = morphset.date().exact('start') or 0
                    end = morphset.date().exact('end') or 0
                if typeunit.wordclass() == 'UH':
                    wordform = make_interjection(typeunit.form)
                else:
                    wordform = typeunit.form

                signature = (wordform, typeunit.wordclass())
                forms[signature].append(FormData(
                    wordform,
                    typeunit.sort,
                    wordclass_set.id,
                    typeunit.id,
                    oed_id,
                    oed_xnode,
                    typeunit.wordclass(),
                    start,
                    end,
                    morphset.types()[0].form,
                    ))

    # Filter so that there's only one example of each form+pos
    return [local_list[0] for local_list in forms.values()]


def _np_handler(wordclass_set):
    omit = set()
    singlewords = []
    multiwords = []
    for morphset in wordclass_set.morphsets():
        for type in morphset.types():
            if type.lemma_manager().num_words() == 1:
                singlewords.append(type.lemma_manager())
            elif type.lemma_manager().num_words() > 1:
                multiwords.append(type.lemma_manager())
    for j in singlewords:
        for k in multiwords:
            if k.words()[-1] == j.lemma:
                omit.add(j.lexical_sort())
    return omit


def make_interjection(form):
    uh_form = form.capitalize()
    if uh_form[-1] in string.ascii_lowercase:
        uh_form += '!'
    return uh_form
