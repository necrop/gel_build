"""
OdoAdditions
"""

import os
import re

from lxml import etree

import gelconfig
from lex.odo.linkmanager import LinkManager
from lex.odo.distiller import Distiller
from lex.oed.daterange import DateRange
from lex.wordclass.wordclass import Wordclass

FILE_SIZE = gelconfig.FILE_SIZE_BUILD
LINK_MANAGERS = {dictname: LinkManager(dictName=dictname)
                 for dictname in ('ode', 'noad')}
DISTILLERS = {dictname: Distiller(dictName=dictname)
              for dictname in ('ode', 'noad')}
START_DATE = gelconfig.DATE_ODO_START
END_DATE = gelconfig.DATE_MAXIMUM

DEFAULT_DATE_NODE = etree.tostring(
    DateRange(start=START_DATE, end=END_DATE, estimated=True)
    .to_xml(omitProjected=True))


class OdoAdditions(object):

    """
    Add entries from ODE and NOAD which have not already been
    accounted for by OED entries (i.e. encyclopedic entries, and anything
    else without a link to OED).
    """

    def __init__(self, dir):
        self.out_dir = dir
        for dictname in ('ode', 'noad'):
            LINK_MANAGERS[dictname].parse_link_file()
            DISTILLERS[dictname].load_distilled_file()
        self.handled = set()
        self.dictname = None
        self.filecount = None

    @property
    def complement(self):
        if self.dictname == 'ode':
            return 'noad'
        elif self.dictname == 'noad':
            return 'ode'
        else:
            return None

    def process(self, dictname):
        self.filecount = 0
        self.dictname = dictname
        self.initialize_doc()
        for entry in DISTILLERS[dictname].entries:
            if (LINK_MANAGERS[dictname].translate_id(entry.lexid) and
                entry.wordclass_blocks[0].wordclass != 'NP'):
                continue
            if entry.lexid in self.handled:
                continue
            if entry.wordclass_blocks[0].wordclass == 'SYM':
                continue

            self.doc.append(self.construct_entry_node(entry))
            self.handled.add(entry.lexid)
            for block in entry.wordclass_blocks:
                if block.complement:
                   self.handled.add(block.complement)

            # Write the buffer to file, then clear the buffer
            if self.buffersize() >= FILE_SIZE:
                self.writebuffer()
                self.initialize_doc()
        # Output anything still left in the buffer at the end
        self.writebuffer()

    def initialize_doc(self):
        self.doc = etree.Element('entries')

    def buffersize(self):
        return len(self.doc)

    def writebuffer(self):
        with open(self.next_filename(), 'w') as filehandle:
            filehandle.write(etree.tostring(self.doc,
                                            pretty_print=True,
                                            encoding='unicode'))

    def next_filename(self):
        self.filecount += 1
        filename = '%s-%04d.xml' % (self.dictname, self.filecount,)
        return os.path.join(self.out_dir, filename)

    def construct_entry_node(self, entry):
        entry_node = etree.Element('e', odoLexid=entry.lexid)
        if entry.wordclass_blocks[0].wordclass == 'NP':
            entry_node.set('encyclopedic', 'true')

        lemma_node = etree.Element('lemma', src=self.dictname)
        lemma_node.text = entry.headword
        if entry.headword_us:
            lemma_node.set('locale', 'uk')
            lemma_node2 = etree.Element('lemma', locale='us', src=self.dictname)
            lemma_node2.text = entry.headword_us
            entry_node.append(lemma_node)
            entry_node.append(lemma_node2)
        else:
            entry_node.append(lemma_node)

        for block in entry.wordclass_blocks:
            # date node
            if entry.date is not None:
                daterange = DateRange(start=entry.date,
                                      end=END_DATE,
                                      estimated=False)
                if block.wordclass == 'NP':
                    daterange.is_estimated = True
                local_date_node = etree.tostring(daterange.to_xml(omitProjected=True))
            elif block.wordclass != 'NP':
                local_date_node = DEFAULT_DATE_NODE
            else:
                local_date_node = None

            wordclass_set_node = etree.SubElement(entry_node, 'wordclassSet')
            wordclass_set_node.append(Wordclass(block.wordclass).to_xml())
            if local_date_node:
                wordclass_set_node.append(etree.fromstring(local_date_node))

            morphsetblock_node = etree.Element('morphSetBlock')
            for morphgroup in block.morphgroups:
                morphset_node = etree.SubElement(morphsetblock_node, 'morphSet')
                if local_date_node:
                    morphset_node.append(etree.fromstring(local_date_node))
                for unit in morphgroup.morphunits:
                    type_node = etree.SubElement(morphset_node, 'type')
                    form_node = etree.SubElement(type_node, 'form')
                    form_node.text = unit.form
                    type_node.append(Wordclass(unit.wordclass).to_xml())

            wordclass_set_node.append(morphsetblock_node)
            wordclass_set_node.append(self.definition_node(block))
            wordclass_set_node.append(self.resource_node(block, entry.lexid))

        return entry_node

    def resource_node(self, block, lexid):
        wrapper_node = etree.Element('resourceSet')
        resource_node1 = etree.Element('resource',
                                       code=self.dictname,
                                       xrid=lexid,
                                       type='entry')
        wrapper_node.append(resource_node1)
        if block.complement:
            resource_node2 = etree.Element('resource',
                                           code=self.complement,
                                           xrid=block.complement,
                                           type='entry')
            wrapper_node.append(resource_node2)
        oed_id = LINK_MANAGERS[self.dictname].translate_id(lexid)
        if oed_id:
            id_parts = oed_id.split('#')
            resource_node3 = etree.Element('resource',
                                           code='oed',
                                           xrid=id_parts[0],
                                           type='entry')
            if len(id_parts) > 1:
                resource_node3.set('xnode', id_parts[1])
            wrapper_node.append(resource_node3)
        return wrapper_node

    def definition_node(self, block):
        wrapper_node = etree.Element('definitions')
        definition_node1 = etree.Element('definition', src=self.dictname)
        definition_node1.text = block.definition
        if re.search(r'\.\.\.$', block.definition):
            definition_node1.set('truncated', 'true')
        wrapper_node.append(definition_node1)
        linked_def = self.linked_definition(block)
        if linked_def:
            definition_node2 = etree.Element('definition', src=self.complement)
            definition_node2.text = linked_def
            if re.search(r'\.\.\.$', linked_def):
                definition_node2.set('truncated', 'true')
            wrapper_node.append(definition_node2)
        return wrapper_node

    def linked_definition(self, block):
        if not block.complement:
            return None
        target = DISTILLERS[self.complement].entry_by_id(block.complement)
        if not target:
            return None

        matching_blocks = [t for t in target.wordclass_blocks
                           if t.wordclass == block.wordclass and t.definition]
        try:
            return matching_blocks[0].definition
        except IndexError:
            return None
