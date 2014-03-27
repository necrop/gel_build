"""
merge_entries
"""

from collections import defaultdict

from lex.gel.fileiterator import FileIterator


def merge_entries(in_dir, out_dir):
    """
    Merge separate GEL entries generated for separate OED entries which
    are really different wordclasses of the same lemma.

    E.g. anger n. and anger v.
    """
    iterator = FileIterator(in_dir=in_dir, out_dir=out_dir, verbosity='low')
    for filecontent in iterator.iterate():
        target_log = set()
        ode_linked_parallels = _find_parallels(filecontent)
        for entry in filecontent.entries:
            target_id = None
            if entry.attribute('parentId'):
                # Avoid loops (two entries treating each other
                #  as parent)
                if not entry.oed_id() in target_log:
                    target_id = entry.attribute('parentId')
                    target_log.add(entry.attribute('parentId'))
            elif entry.oed_lexid() in ode_linked_parallels:
                target_id = ode_linked_parallels[entry.oed_lexid()]

            if target_id:
                targets = filecontent.entry_by_id(target_id)
                targets = [t for t in targets if t.tag() == 's1']
                if targets:
                    for wc in entry.wordclass_sets():
                        targets[0].node.append(wc.node)
                    entry.node.getparent().remove(entry.node)


def _find_parallels(fileset):
    """
    Find pairs of entries which share the same lemma and link to
    the same ODE entry; this implies that they are really different
    wordclasses of the same lemma.
    """
    # Sort entries into groups which share the same lemma and link
    #  to the same ODE entry
    entry_groups = defaultdict(lambda: defaultdict(list))
    for entry in [e for e in fileset.entries if e.tag() == 's1' and
                  len(e.wordclass_sets()) == 1]:
        ode_link = entry.wordclass_sets()[0].link(target='ode')
        if ode_link:
            entry_groups[entry.lemma][ode_link].append(entry)

    # Find groups with two or more members
    groups = []
    for z in entry_groups.values():
        groups.extend([group for group in z.values() if len(group) > 1])

    parallels = {}
    for group in groups:
        # Check that each member of the group represents a different
        #  wordclass
        wordclasses = set([e.primary_wordclass() for e in group])
        if len(wordclasses) != len(group):
            continue
        # Skip if these are already linked together by parentId - since
        #  these will be caught separately
        if any([e.attribute('parentId') for e in group]):
            continue
        for entry in group[1:]:
            parallels[entry.oed_lexid()] = group[0].oed_lexid()
    return parallels

