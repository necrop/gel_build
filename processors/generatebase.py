"""
GenerateBase - Generates the base data files for GEL
"""

import os
import re

from lxml import etree

import gelconfig
from lex.entryiterator import EntryIterator
from lex.oed.variants.variantscomputer import VariantsComputer
from lex.oed.daterange import DateRange
from lex.oed.lemmawithvariants import LemmaWithVariants
from lex.odo.linkmanager import LinkManager
from lex.inflections.spellingconverter import SpellingConverter
from lex.wordclass.wordclass import Wordclass

# number of entries per output file
FILESIZE = gelconfig.FILE_SIZE_BUILD
ENTRY_SIZE_MINIMUM = gelconfig.MINIMUM_NUM_QUOTATIONS
DEFINITION_LENGTH = gelconfig.DEFINITION_LENGTH

SPECULATIVE_START = gelconfig.DATE_SPECULATIVE_START
SPECULATIVE_END = gelconfig.DATE_SPECULATIVE_END
US_VARIANT_MINIMUM = gelconfig.VAR_US_MINIMUM
MINIMUM_DATE = gelconfig.DATE_MINIMUM

LINK_MANAGERS = {dictname: LinkManager(dictName=dictname)
                 for dictname in ('ode', 'noad')}
SPELLING_CONVERTER = SpellingConverter()
SPLIT_CORRECTORS = (
    re.compile(r'([bdfglmnprstz])~\1(ing|ed|er|ery|ish)$'),
    re.compile(r'([bdfgmprstz])~\1(ess)$'),
)


class GenerateBase(object):

    def __init__(self, dir):
        self.out_dir = dir
        self.filecount = 0
        self.entry = None
        self.root = None

    def clear_outdir(self):
        for filename in os.listdir(self.out_dir):
            os.unlink(os.path.join(self.out_dir, filename))

    def initialize_root(self):
        self.root = etree.Element('entries')

    def buffersize(self):
        return len(self.root)

    def process(self):
        self.clear_outdir()
        self.initialize_root()
        previous = None
        iterator = EntryIterator(dict_type='oed',
                                 verbosity='low',
                                 fix_ligatures=True)

        # Iterate through all entries in OED, processing each and storing
        #   the results in a buffer
        for entry in iterator.iterate():
            self.entry = entry

            # Write the buffer to a file when it gets to a certain size, and
            #   there's an appropriate break, e.g. not in the middle
            #   of homographs.
            if (self.buffersize() >= FILESIZE and
                    entry.lemma_manager().lexical_sort() != previous):
                self.writebuffer()
                self.initialize_root()

            # Process the current entry -> buffer
            self.process_entry()

            # Keep track of the previous entry's headword (to help find a good
            #   opportunity to write the buffer to a file)
            previous = entry.lemma_manager().lexical_sort()

        # Write a file for anything still left in the buffer after the
        #  entry iterator has completed
        self.writebuffer()

    def process_entry(self):
        # Make sure <s1> blocks know what entry their parent entry
        #   is paired with (if any): set a 'pair_id' attribute.
        if self.entry.paired_with():
            for block in self.entry.s1blocks():
                block.paired_entry_id = self.entry.paired_with()

        # Process each s1 block
        for block in self.entry.s1blocks():
            self.process_block(block)
        # Process each sense or subentry that represents a distinct lemma
        for sense in self.entry.lemma_senses_uniq():
            self.process_block(sense)

    def process_block(self, block):
        """
        Process an individual block (may be a <s1> block or a subentry).
        """
        # If this is an unevidenced subentry, set the dates to the
        #  publication date of the parent entry
        if ((not block.date().start or block.date().start > 2050)
                and self.entry.first_published()):
            block.date().reset('start', self.entry.first_published())
            block.date().reset('end', self.entry.first_published())

        # Bug out if this block is not usable
        if (not block.primary_wordclass().penn or
                block.lemma_manager().is_affix() or
                block.lemma.lower().startswith('the ') or
                block.is_initial_letter() or
                block.is_cross_reference() or
                not block.date().start or
                block.num_quotations() < ENTRY_SIZE_MINIMUM):
            return
        if block.tag == 's1' and block.num_quotations() == 0:
            return

        if block.tag == 's1':
            block.parent_id = self.entry.paired_with()
        elif block.tag == 'sub' and block.lemma == self.entry.headword:
            block.parent_id = self.entry.s1blocks()[0].node_id()
        else:
            block.parent_id = None

        # Add a '~' into closed compounds/derivatives, to enable
        #  variation to be applied to individual components.
        self.split_compound(block)

        gel_block = GelBlock(block, self.entry)
        gel_block.set_dates()
        gel_block.assign_wordclasses()
        node = gel_block.construct_entry_node()
        if gel_block.is_usable():
            self.root.append(node)

    def split_compound(self, block):
        """
        Determine whether the lemma is a closed compound; in which case
        it gets (temporarily) split with a '~' as a separator. This enables
        variation to be applied to individual components.
        """
        if not block.lemma_manager().is_compound():
            new_lemma = None
            if (block.tag == 's1' and
                self.entry.etymology().is_compound(headword=block.lemma)):
                new_lemma = split_closed_compound(block.lemma,
                            self.entry.etymology().etyma()[0].lemma)
            elif not block.tag == 's1':
                new_lemma = split_closed_compound(block.lemma,
                            self.entry.headword)
            if new_lemma and not new_lemma == block.lemma:
                block.set_lemma(LemmaWithVariants(new_lemma))

    def writebuffer(self):
        with open(self.next_filename(), 'w') as filehandle:
            filehandle.write(etree.tostring(self.root,
                                            pretty_print=True,
                                            encoding='unicode'))

    def next_filename(self):
        self.filecount += 1
        filename = '%04d.xml' % (self.filecount,)
        return os.path.join(self.out_dir, filename)


class GelBlock(object):

    def __init__(self, block, entry):
        self.block = block
        self.entry = entry
        self.wordclass = None
        if self.block.is_revised:
            self.src_type = 'oed_rev'
        else:
            self.src_type = 'oed_unrev'
        self._linked_ids = {}

    @property
    def type(self):
        if self.block.tag == 's1':
            return 's1'
        else:
            return 'sense'

    def long_id(self):
        if self.type == 's1':
            return self.block.id
        else:
            return self.block.id + '#' + self.block.node_id()

    def set_dates(self):
        if self.block.date().start == 0:
            self.block.date().reset('start', SPECULATIVE_START)
            self.block.date().reset('end', SPECULATIVE_END)
            self.block.date().is_estimated = True
        else:
            self.block.date().last_documented = self.block.date().end

    def assign_wordclasses(self):
        self.wordclasses = []
        for wordclass_manager in self.block.wordclasses():
            self.wordclasses.append(self.adjust_wordclass_to_ode(wordclass_manager))
        if not self.wordclasses:
            self.wordclasses.append(Wordclass('NN'))

        # Watch out for sense-level items which end up with
        #   too many wordclasses; these are probably erroneous (like
        #   'all-cargo' or 'all-accomplished', which for some reason have
        #   all the wordclasses of the parent entry)
        if self.type == 'sense' and len(self.wordclasses) > 2:
            penn_values = [wc.penn for wc in self.wordclasses]
            chosen_wordclass = None
            for penn in penn_values:
                if penn == 'NN' or penn == 'JJ':
                    chosen_wordclass = Wordclass(penn)
                    break
            if not chosen_wordclass and 'RB' in penn_values:
                chosen_wordclass = Wordclass('RB')
            elif not chosen_wordclass:
                chosen_wordclass = self.wordclasses[0]
            self.wordclasses = [chosen_wordclass, ]

    def adjust_wordclass_to_ode(self, wordclass_manager):
        """
        If the wordclass (according to OED) is 'NN', check the entry it's
        linked to in ODE or NOAD, and change the wordclass to 'NNS' if
        necessary. (This fixes things like 'trousers', 'acrobatics', etc.)
        """
        if wordclass_manager.penn == 'NN':
            if self.linked_entry_id('ode'):
                target_id = self.linked_entry_id('ode')
                target_entry = LINK_MANAGERS['ode'].find_content(target_id)
                if (target_entry and
                        target_entry.wordclass_blocks[0].wordclass == 'NNS'):
                    return Wordclass('NNS')
            elif self.linked_entry_id('noad'):
                target_id = self.linked_entry_id('noad')
                target_entry = LINK_MANAGERS['noad'].find_content(target_id)
                if (target_entry and
                        target_entry.wordclass_blocks[0].wordclass == 'NNS'):
                    return Wordclass('NNS')
        return wordclass_manager

    def construct_entry_node(self):
        entry_node = etree.Element('e',
                                   oedId=str(self.block.id),
                                   oedLexid=str(self.block.node_id()),
                                   tag=self.block.tag)

        if self.block.tag == 's1':
            if self.block.parent_id:
                parent_id = self.block.parent_id
            elif self.block.first_sibling is not None:
                parent_id = self.block.first_sibling
            else:
                parent_id = None
            if parent_id:
                entry_node.set('parentId', str(parent_id))
        elif self.block.tag == 'sub' and self.block.parent_id:
            entry_node.set('parentId', str(self.block.parent_id))

        for l in self.lemma_fragments():
            entry_node.append(l)

        for wordclass_manager in self.wordclasses:
            if not wordclass_manager.penn:
                continue
            self.wordclass = wordclass_manager.penn

            # Compute the set of variants appropriate to this lemma
            # in this wordclass
            if self.type == 's1':
                primary_id = self.entry.id
                hint_ids = self.entry.etymology().etyma_targets()
                etyma = self.entry.etymology().etyma_lemmas()
            else:
                primary_id = None
                hint_ids = [self.entry.id, ]
                etyma = []
            headwords = [l['lemma'] for l in self.entry_lemmas()]
            varcomputer = VariantsComputer(lemma=self.block.lemma,
                                           wordclass=self.wordclass,
                                           headwords=headwords,
                                           id=primary_id,
                                           daterange=self.block.date())
            varcomputer.set_hint_ids(hint_ids)
            varcomputer.set_etyma(etyma)
            varcomputer.compute()
            local_lemma_manager = varcomputer.lemma_manager

            wordclass_node = etree.Element('wordclassSet')
            wordclass_node.append(wordclass_manager.to_xml())
            wordclass_node.append(self.block.date().to_xml(omitProjected=True))

            morphset_block_node = etree.Element('morphSetBlock')
            for variant_form in local_lemma_manager.variants:
                seen = set()
                variant_form_fixed = unswung(variant_form.form)
                if not variant_form_fixed in seen:
                    morphset_node = etree.SubElement(morphset_block_node,
                                                     'morphSet')
                    if variant_form.irregular:
                        morphset_node.set('irregular', 'true')
                    if variant_form.regional:
                        morphset_node.set('regional', 'true')

                    # Date node for the variant form
                    vardate_node = _variant_date_node(variant_form.date,
                                                      self.block.date())
                    morphset_node.append(vardate_node)

                    # Put a single type in the morphset, representing
                    #  the base form.
                    # Later this will be replaced by a series of types
                    #  representing the full set of inflections.
                    type_node = etree.SubElement(morphset_node, 'type')
                    form_node = etree.SubElement(type_node, 'form')
                    form_node.text = variant_form_fixed
                    if variant_form.computed:
                        type_node.set('computed', 'true')
                    type_node.append(wordclass_manager.to_xml())
                    seen.add(variant_form_fixed)

            wordclass_node.append(morphset_block_node)
            wordclass_node.append(self.build_definition_node())
            wordclass_node.append(self.build_resource_node())

            entry_node.append(wordclass_node)
        return entry_node

    def is_usable(self):
        usable = True
        for dictname in [d for d in ('ode', 'noad') if self.linked_entry_id(d)]:
            target_id = self.linked_entry_id(dictname)
            target_entry = LINK_MANAGERS[dictname].find_content(target_id)
            if target_entry and target_entry.wordclass_blocks[0].wordclass == 'NP':
                usable = False
        if (self.type == 's1' and
                re.search(r'^[A-Z][a-z]', self.block.lemma_manager().asciified()) and
                not any([self.block.lemma_manager().lexical_sort() == sense.lemma_manager().lexical_sort()
                         for sense in self.block.senses()])):
            usable = False
        if self.block.date().end <= MINIMUM_DATE:
            usable = False
        return usable

    def linked_entry_id(self, dictname):
        if not self._linked_ids:
            self._compile_linked_ids()
        try:
            return self._linked_ids[dictname]
        except KeyError:
            return None

    def _compile_linked_ids(self):
        self._linked_ids = {}
        for dictname in LINK_MANAGERS:
            lm = LINK_MANAGERS[dictname]
            target_id = lm.translate_id(self.long_id())
            # If the entry's own ID has failed, try again with the ID
            #  of the entry that it's paired with (if any)
            if not target_id:
                try:
                    self.block.paired_entry_id
                except AttributeError:
                    pass
                else:
                    target_id = lm.translate_id(self.block.paired_entry_id)
            if target_id:
                self._linked_ids[dictname] = target_id
            else:
                self._linked_ids[dictname] = None

    def build_resource_node(self):
        resourceset_node = etree.Element('resourceSet')

        # Link to OED
        if self.block.tag == 's1':
            block_type = 'entry'
        else:
            block_type = 'subentry'
        oed_node = etree.Element('resource',
                                 code='oed',
                                 xrid=str(self.block.id),
                                 xnode=str(self.block.node_id()),
                                 type=block_type)
        resourceset_node.append(oed_node)

        # Links to ODE and/or NOAD
        for dictname in ('ode', 'noad'):
            if self.linked_entry_id(dictname):
                target_id = self.linked_entry_id(dictname)
                xnode = None
            else:
                target_id, xnode = LINK_MANAGERS[dictname].find_derivative(
                    self.block.lemma,
                    self.wordclass,
                    self.block.date().last_documented,
                    )
            if target_id is not None:
                resource_node = etree.Element('resource',
                                              code=dictname,
                                              xrid=target_id)
                if xnode is None:
                    resource_node.set('type', 'entry')
                else:
                    resource_node.set('xnode', xnode)
                    resource_node.set('type', 'subentry')
                resourceset_node.append(resource_node)
        return resourceset_node

    def build_definition_node(self):
        definition_node = etree.Element('definitions')
        for dictname in ('ode', 'noad', self.src_type):
            def_text = self.definition_text(dictname)
            if def_text:
                dnode = etree.Element('definition', src=dictname)
                dnode.text = def_text
                if re.search(r'\.\.\.$', def_text):
                    dnode.set('truncated', 'true')
                definition_node.append(dnode)
        return definition_node

    def definition_text(self, dictname):
        if dictname == 'oed_rev' or dictname == 'oed_unrev':
            return self.block.definition(
                length=DEFINITION_LENGTH,
                current=True,
                )
        elif self.linked_entry_id(dictname):
            return LINK_MANAGERS[dictname].find_definition(
                self.linked_entry_id(dictname),
                wordclass=self.wordclass,
                )
        else:
            return None

    def entry_lemmas(self):
        lemmas = []
        if self.ode_lemmas('uk') and self.ode_lemmas('us'):
            for locale in ('uk', 'us'):
                lemmas.append({
                    'lemma': self.ode_lemmas(locale),
                    'locale': locale,
                    'source': 'ode'})
        elif self.ode_lemmas('default'):
            lemmas.append({
                'lemma': self.ode_lemmas('default'),
                'locale': None,
                'source': 'ode'})
        elif self.noad_lemmas('default'):
            lemmas.append({
                'lemma': self.noad_lemmas('default'),
                'locale': None,
                'source': 'noad'})
        else:
            lemma_us = SPELLING_CONVERTER.us_spelling(self.block.lemma)
            if (lemma_us != self.block.lemma and
                self.block.date().projected_end() >= US_VARIANT_MINIMUM):
                lemmas.append({
                    'lemma': unswung(self.block.lemma),
                    'locale': 'uk',
                    'source': self.src_type})
                lemmas.append({
                    'lemma': unswung(lemma_us),
                    'locale': 'us',
                    'source': self.src_type})
            else:
                lemmas.append({
                    'lemma': unswung(self.block.lemma),
                    'locale': None,
                    'source': self.src_type})
        return lemmas

    def ode_lemmas(self, locale):
        return self.odo_lemmas('ode', locale)

    def noad_lemmas(self, locale):
        return self.odo_lemmas('noad', locale)

    def odo_lemmas(self, dictname, locale):
        try:
            self._odo_lemmas
        except AttributeError:
            self._odo_lemmas = _compile_odo_lemmas(
                                    ode_link=self.linked_entry_id('ode'),
                                    noad_link=self.linked_entry_id('noad'))
        return self._odo_lemmas[dictname][locale]

    def lemma_fragments(self):
        fragments = []
        for j in self.entry_lemmas():
            fragment = etree.Element('lemma', src=j['source'])
            fragment.text = j['lemma']
            if j['locale'] is not None:
                fragment.set('locale', j['locale'])
            fragments.append(fragment)
        return fragments


def split_closed_compound(lemma, referent_lemma):
    if referent_lemma.endswith('-') or len(referent_lemma) < 3:
        return lemma
    referent_lemma = re.sub(r'[()\[\]]', '', referent_lemma)
    pattern = re.compile('^(' + referent_lemma + ')([a-z]{3,}|ed|er)$', re.I)
    lemma_new = pattern.sub(r'\1~\2', lemma)

    # Test for and correct mis-split doubled consonants
    if not lemma_new == lemma:
        for split_pattern in SPLIT_CORRECTORS:
            if split_pattern.search(lemma_new):
                lemma_new = re.sub(r'~(.)', r'\1~', lemma_new)

    return lemma_new


def unswung(lemma):
    """
    Return new version of the lemma in which digraphs have been replaced.
    and swung dash removed.
    """
    replacements = (
        ('\u009c', 'oe'),
        ('\u008c', 'Oe'),
        ('\u00e6', 'ae'),
        ('\u00c6', 'Ae'),
        ('~', ''),
    )
    for replacement in replacements:
        lemma = lemma.replace(replacement[0], replacement[1])
    return lemma


def _compile_odo_lemmas(**kwargs):
    links = {'ode': kwargs.get('ode_link'),
             'noad': kwargs.get('noad_link'),}

    output = {}
    for dictname in ('ode', 'noad'):
        lemmas = {'default': None, 'uk': None, 'us': None}
        if links[dictname]:
            for locale in ('uk', 'us'):
                lemmas[locale] = LINK_MANAGERS[dictname].find_lemma(
                    links[dictname],
                    locale=locale,)
            if dictname == 'ode' and not lemmas['us'] and lemmas['uk']:
                l1 = lemmas['uk']
                l2 = SPELLING_CONVERTER.us_spelling(l1)
                if l1 == l2:
                    lemmas['default'] = l1
                    lemmas['uk'] = None
                else:
                    lemmas['uk'] = l1
                    lemmas['us'] = l2
            elif dictname == 'noad' and lemmas['us'] and not lemmas['uk']:
                lemmas['default'] = lemmas['us']
                lemmas['us'] = None
            elif dictname == 'noad' and lemmas['uk'] and not lemmas['us']:
                lemmas['default'] = lemmas['uk']
                lemmas['uk'] = None
        output[dictname] = lemmas

    return output


def _variant_date_node(variant_date, block_date):
    """
    Return a date-range node for a variant form
    """
    # Constrain the variant's dates, so that they don't
    # fall outside the limits of the parent entry
    start_date, end_date = variant_date.constrain((
        block_date.start,
        block_date.projected_end(),
    ))
    # Create a new date range with the constrained dates
    constrained_date_range = DateRange(start=start_date,
                                       end=end_date,
                                       hardEnd=True)
    return constrained_date_range.to_xml(omitProjected=True)