"""Independent synthetic CFG counterexamples and immutable empirical map guards.
No protected PHP (or reconstructed candidate) is executed.
"""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.readonly_dataflow import read_definitions, analyze_file, _validated_evidence


def unused(word0=0, word1=0):
    return {'type':8,'word0':word0,'word1':word1}


def temporary(number=0):
    return {'type':2,'word0':number,'word1':0}


def constant(value=1):
    return {'type':1,'constant':{'kind':'integer','value':value}}


def instruction(index,opcode,*,result=None,op1=None,op2=None):
    return {'index':index,'decoded_opcode':opcode,'result':result or unused(),
            'op1':op1 or unused(),'op2':op2 or unused(),
            'extended_value':0,'line':index+1}


class EntryBackedgeTests(unittest.TestCase):
    def test_loop_entry_is_merged_with_virtual_undefined_predecessor(self):
        # The read at #0 is undefined on first entry and has producer #1 on
        # repeated entries. The previous implementation incorrectly reported no reaching definition.
        group={'opcodes':[
            instruction(0,40,op1=temporary()),
            instruction(1,52,result=temporary(),op1=constant()),
            instruction(2,43,op1=constant(),op2=unused(0,1)),
            instruction(3,62,op1=constant())]}
        report=read_definitions(group)
        self.assertEqual(report['status'],'analyzed_syntactically')
        row=report['temporary_uses'][0]
        self.assertEqual(row['reaching_definition_indices'],[-1,1])
        self.assertEqual(row['status'],'possibly_undefined')

    def test_non_entry_loop_does_not_get_spurious_undefined(self):
        group={'opcodes':[
            instruction(0,52,result=temporary(),op1=constant()),
            instruction(1,42,op1=unused(2,1)),
            instruction(2,40,op1=temporary()),
            instruction(3,43,op1=constant(),op2=unused(2,1)),
            instruction(4,62,op1=constant())]}
        report=read_definitions(group)
        row=report['temporary_uses'][0]
        self.assertEqual(row['reaching_definition_indices'],[0])
        self.assertEqual(row['status'],'one_reaching_definition_syntactic_only')

    def test_unknown_opcode_remains_fail_closed(self):
        report=read_definitions({'opcodes':[instruction(0,None)]})
        self.assertEqual(report['status'],'unsupported')


class EvidenceIntegrityTests(unittest.TestCase):
    def test_verified_map_and_evidence_have_consistent_hashes(self):
        evidence=_validated_evidence(OPCODE_MAP)
        self.assertEqual(evidence['6:226']['status'],'unknown')
        self.assertEqual(evidence['1:199']['opcode'],None)

    def test_tampered_mapping_is_not_used_for_dataflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/OPCODE_MAP.name
            path.write_bytes(OPCODE_MAP.read_bytes()+b'\n')
            (Path(tmp)/(path.name+'.meta.json')).write_bytes(
                OPCODE_METADATA.read_bytes())
            with self.assertRaisesRegex(ValueError,'mapping/metadata SHA256 mismatch'):
                _validated_evidence(path)

    def test_unknown_140_in_real_link_file_is_not_cfg_evidence(self):
        report=analyze_file(ROOT/'sample_inputs'/'links_fun(1).php',
                            ROOT/'zend_verified_dictionary.bin',
                            OPCODE_MAP)
        main=report['groups'][0]
        self.assertEqual(main['status'],'unsupported')
        self.assertIn(14,main['unknown_indices'])
        self.assertEqual(main['uncertain_opcodes'][0]['key'],'6:226')
        self.assertFalse(report['php_generated'])

if __name__=='__main__':unittest.main()
