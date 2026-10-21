"""Read-only static diagnostics. Never executes encoded or reconstructed PHP."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.readonly_dataflow import Operand, read_definitions, analyze_file
from zend_decompiler.alignment_audit import audit_alignment, TRACE_LOCATIONS


def const(value=1):
    return {'type':1,'constant':{'kind':'integer','value':value}}

def unused(num=0,word1=0):
    return {'type':8,'word0':num,'word1':word1}

def tmp(num=0):
    return {'type':2,'word0':num,'word1':0}

def ins(index, opcode, result=None, op1=None, op2=None):
    return {'index':index,'decoded_opcode':opcode,'result':result or unused(),
            'op1':op1 or unused(), 'op2':op2 or unused(), 'extended_value':0,'line':index+1}


class ReadOnlyDataflowTests(unittest.TestCase):
    def test_operand_is_typed_and_lossless(self):
        op=Operand.from_node(tmp(27))
        self.assertEqual(op.kind,'temporary')
        self.assertEqual(op.definition_key(),(2,27,0))
        c=Operand.from_node({'type':1,'constant':{'kind':'string','raw_hex':'00ff'}})
        self.assertEqual(c.raw_constant['raw_hex'],'00ff')

    def test_single_crossblock_definition_is_only_syntactic(self):
        ops=[ins(0,52,result=tmp(0),op1=const()),
             ins(1,42,op1=unused(3,1)),
             ins(2,52,result=tmp(0),op1=const(2)),
             ins(3,40,op1=tmp(0)),ins(4,62,op1=const())]
        report=read_definitions({'opcodes':ops},title='synthetic')
        entry=next(r for r in report['temporary_uses'] if r['instruction_index']==3)
        self.assertEqual(entry['reaching_definition_indices'],[0])
        self.assertTrue(entry['cross_block'])
        self.assertIn('syntactic_only',entry['status'])

    def test_branch_merge_never_selects_arbitrary_definition(self):
        ops=[ins(0,43,op1=const(),op2=unused(3,1)),
             ins(1,52,result=tmp(0),op1=const()),
             ins(2,42,op1=unused(4,1)),
             ins(3,52,result=tmp(0),op1=const(2)),
             ins(4,40,op1=tmp(0)),ins(5,62,op1=const())]
        report=read_definitions({'opcodes':ops})
        entry=next(r for r in report['temporary_uses'] if r['instruction_index']==4)
        self.assertEqual(entry['status'],'multiple_reaching_definitions')
        self.assertEqual(entry['reaching_definition_indices'],[1,3])

    def test_uninitialized_and_unknown_fail_closed(self):
        report=read_definitions({'opcodes':[ins(0,40,op1=tmp(99)),ins(1,62,op1=const())]})
        self.assertEqual(report['temporary_uses'][0]['status'],'no_reaching_definition')
        report=read_definitions({'opcodes':[ins(0,None)]})
        self.assertEqual(report['status'],'unsupported')

    def test_real_out_link_has_two_syntactic_producers(self):
        rep=analyze_file(ROOT/'sample_inputs'/'fun_all.php',
                         ROOT/'zend_verified_dictionary.bin',OPCODE_MAP)
        out=next(x for x in rep['groups'] if x['group']=='out_link')
        row=next(x for x in out['temporary_uses'] if x['instruction_index']==16 and x['operand']=='op1')
        self.assertEqual(row['slot'],[2,0,0])
        self.assertEqual(row['reaching_definition_indices'],[13,15])
        self.assertEqual(row['status'],'multiple_reaching_definitions')
        self.assertFalse(rep['php_generated'])


class ArchivedAlignmentTests(unittest.TestCase):
    def test_report_records_mismatches_without_promoting_opcodes(self):
        data=json.loads((ALIGNMENT_FIXTURE).read_text(encoding='utf-8'))
        self.assertEqual(data['serialized_instructions'],4204)
        self.assertEqual(data['group_count'],34)
        self.assertEqual(data['alignment_status_counts']['mapped_mismatch'],2)
        self.assertEqual(data['alignment_status_counts']['unmapped'],2)
        self.assertEqual(len(data['critical_unresolved']['1:199']['records']),2)
        self.assertTrue(all(r['mapped'] is None for r in data['critical_unresolved']['1:199']['records']))
        self.assertFalse(any(v.get('archived_trace_consistent') for k,v in data['key_audit'].items() if k in ('3:139','6:236')))

    def test_optional_saved_trace_recalculation(self):
        # Do not ship sensitive probe logs: they may include
        # user program literals. Run locally when the original saved logs exist.
        root=Path('/mnt/data')
        if not all((root/relative).exists() for relative in TRACE_LOCATIONS.values()):
            self.skipTest('Historical diagnostic traces not present in package')
        fresh=audit_alignment(ROOT,root)
        stored=json.loads((ALIGNMENT_FIXTURE).read_text(encoding='utf-8'))
        self.assertEqual(fresh,stored)

if __name__=='__main__':unittest.main()
