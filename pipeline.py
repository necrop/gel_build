"""
pipeline - pipeline for managing GEL build processes
"""

import os

import gelconfig


def dispatch():
    """
    Run each function listed in the config
    """
    for function_name, run_this in gelconfig.PIPELINE:
        if run_this:
            print('=' * 30)
            print('Running "%s"...' % (function_name,))
            print('=' * 30)
            func = globals()[function_name]
            func()


def distilOdo():
    from lex.odo.distiller import Distiller
    definition_length = gelconfig.DEFINITION_LENGTH
    Distiller(dictName='ode', defLength=definition_length).distil()
    Distiller(dictName='noad', defLength=definition_length).distil()


def generateMorphologyHub():
    from lex.inflections.mmh.mmhwriter import MmhWriter
    hubwriter = MmhWriter()
    hubwriter.load_morphgroups()
    hubwriter.write_morphgroups()


def updateLinkTables():
    from processors.linktableupdater import update_tables, infer_noad
    update_tables()
    infer_noad()


def indexOedSize():
    from frequency.oedsize.oedentrysize import build_weighted_size_index
    build_weighted_size_index()


def generateBase():
    from processors.generatebase import GenerateBase
    processor = GenerateBase(os.path.join(gelconfig.BUILD_DIR, '01_base'))
    processor.process()

    from processors.indexbuildfiles import index_build_files
    index_build_files(os.path.join(gelconfig.BUILD_DIR, '01_base'),
                      os.path.join(gelconfig.BUILD_DIR, 'index.csv'))


def mergeEntryPairs():
    from processors.mergeentries import merge_entries
    merge_entries(os.path.join(gelconfig.BUILD_DIR, '01_base'),
                  os.path.join(gelconfig.BUILD_DIR, '02_defragmented'))


def addInflections():
    from processors.addinflections import add_inflections
    add_inflections(os.path.join(gelconfig.BUILD_DIR, '02_defragmented'),
                    os.path.join(gelconfig.BUILD_DIR, '03_inflected'))

    from processors.addmissinginflections import add_missing_inflections
    add_missing_inflections(os.path.join(gelconfig.BUILD_DIR, '03_inflected'),
                            os.path.join(gelconfig.BUILD_DIR, '04_inflected_ext'))


def addOdoContent():
    from processors.odoadditions import OdoAdditions
    processor = OdoAdditions(os.path.join(gelconfig.BUILD_DIR, '04_inflected_ext'))
    processor.process('ode')
    processor.process('noad')


def cleanAttributes():
    from processors.cleanattributes import clean_attributes
    clean_attributes(os.path.join(gelconfig.BUILD_DIR, '04_inflected_ext'),
                     os.path.join(gelconfig.BUILD_DIR, '05_cleanattributes'))


def frequencyListLemmas():
    from processors.computefrequency import list_lemmas
    list_lemmas(os.path.join(gelconfig.BUILD_DIR, '05_cleanattributes'))


def frequencyCompileNgrams():
    from processors.computefrequency import compile_ngrams
    compile_ngrams()


def frequencyCheckGaps():
    from processors.computefrequency import check_for_missing_ngrams
    check_for_missing_ngrams()


def frequencyRecompilePredictors():
    from processors.computefrequency import compile_regression_data
    compile_regression_data()


def frequencyComputeScores():
    from processors.computefrequency import compute_frequencies
    compute_frequencies()


def insertFrequency():
    from processors.insertfrequency import insert_frequency
    insert_frequency(os.path.join(gelconfig.BUILD_DIR, '05_cleanattributes'),
                     os.path.join(gelconfig.BUILD_DIR, '06_frequency'),
                     os.path.join(gelconfig.FREQUENCY_BUILD_DIR, 'types_with_frequency'))


def alphabetizeOutput():
    from processors.alphasort import AlphaSort
    processor = AlphaSort(os.path.join(gelconfig.BUILD_DIR, '06_frequency'),
                          gelconfig.FINAL_DATA_DIR)
    processor.process()


def indexOutput():
    from processors.buildindex import BuildIndex
    processor = BuildIndex(gelconfig.FINAL_DATA_DIR,
                           os.path.join(gelconfig.FINAL_ANCILLARY_DIR, 'index'))
    processor.process()


if __name__ == '__main__':
    dispatch()
