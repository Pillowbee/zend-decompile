"""No execution of PHP. Synthetic graph and real serialized *static* checks."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.ir_evidence import (php_mask,source_hints,neighborhood,
                                  short_circuit_candidates,produce)


def unused(n=0,mark=0):
    return {'type':8,'word0':n,'word1':mark}


def tmp(n=0):
    return {'type':2,'word0':n,'word1':0}


def const(n=1):
    return {'type':1,'constant':{'kind':'integer','value':n}}


def ins(i,opcode,op1=None,op2=None,result=None):
    return {'index':i,'decoded_opcode':opcode,'encoded_opcode':i+1,
            'op1':op1 if op1 is not None else unused(),
            'op2':op2 if op2 is not None else unused(),
            'result':result if result is not None else unused(),
            'line':i+1,'extended_value':0}


class SourceHintsTests(unittest.TestCase):
    def test_inline_javascript_function_not_counted_as_php(self):
        example='<?php function a(){ foreach($rows as $x){} } ?>\n'
        example+=' <script>function evil(){}</script>\n'
        example+='<? function b(){return 1;} ?>'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'short.php';path.write_text(example,encoding='cp1251')
            result=source_hints(path)
        self.assertEqual(result['function_count_lexical'],2)
        self.assertEqual(sorted(result['functions']),['a','b'])
        self.assertTrue(result['functions']['a']['contains_foreach_keyword'])
        self.assertFalse(result['functions']['b']['contains_foreach_keyword'])
        self.assertNotIn('evil',result['functions'])

    def test_no_source_literals_copied_into_output(self):
        private='UNIQUE_SECRET_CANARY_467201'
        sample=f'<?php function f() {{ $password="{private}"; }} ?>'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fixture.php';path.write_text(sample)
            result=source_hints(path)
        self.assertNotIn(private,json.dumps(result))
        self.assertEqual(result['sha256'],hashlib.sha256(sample.encode()).hexdigest())

    def test_neighborhood_key_uses_index_mod8(self):
        ops=[ins(i,66) for i in range(3)]
        obs=neighborhood(ops,1)
        self.assertEqual([r.get('key') for r in obs['window']],
                         [None,'0:1','1:2','2:3',None])
        self.assertEqual(obs,neighborhood(ops,1))

    def test_foreach_synthetic_key_context_does_not_prove_semantics(self):
        # A deterministic *synthetic* stream mimicking observed neighborhood.
        # The opcode assignment is deliberately never part of this test.
        ops=[ins(i,0) for i in range(12)]
        for i, encoded in [(7,98),(8,24),(9,199),(10,42),(11,9)]:
            ops[i]['encoded_opcode']=encoded
        seen=neighborhood(ops,9)
        self.assertEqual([x['key'] for x in seen['window']],
                         ['7:98','0:24','1:199','2:42','3:9'])
        # Same bytes but a different operand type => different shape.
        ops[9]['op2']=const(0)
        self.assertNotEqual(seen['fingerprint_sha256'],
                            neighborhood(ops,9)['fingerprint_sha256'])

    def test_lexical_comments_cannot_create_fake_function_or_foreach(self):
        src = (
            '<?php /* function fake(){ foreach($secret as $x){} } */\n'
            'function real(){ // foreach($x as $y)\n'
            '  $s="foreach($x as $y)"; foreach($real as $item){}\n}'
        )
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'own.php';path.write_text(src)
            hints=source_hints(path)
        self.assertEqual(hints['function_count_lexical'],1)
        self.assertEqual(hints['functions']['real']['possible_foreach_keyword_count'],1)


class ShortCircuitShapeTests(unittest.TestCase):
    def synthetic(self,code=46,boolean_result=None):
        return {'opcodes':[
            ins(0,17,result=tmp(),op1=const(),op2=const()),
            ins(1,code,op1=tmp(),op2=unused(3,1),result=tmp()),
            ins(2,52,op1=const(),result=boolean_result or tmp()),
            ins(3,43,op1=tmp(),op2=unused(5,1)),
            ins(4,0),
            ins(5,62,op1=const())]}

    def test_two_producers_have_witness_paths(self):
        rows=short_circuit_candidates(self.synthetic())
        self.assertEqual(len(rows),1)
        item=rows[0]
        self.assertEqual((item['jump_instruction'],item['boolean_instruction'],item['join_instruction']), (1,2,3))
        self.assertEqual(item['reaching_definition_indices'],[1,2])
        self.assertFalse(item['emit_php_permitted'])
        self.assertEqual({w['definition_index'] for w in item['structural_path_witnesses']}, {1,2})

    def test_jmpnz_ex_pattern_is_neutral(self):
        rows=short_circuit_candidates(self.synthetic(code=47))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['jump_native_hypothesis'],47)
        self.assertNotIn('&&',json.dumps(rows))
        self.assertNotIn('||',json.dumps(rows))

    def test_false_positive_mismatching_slot_is_rejected(self):
        self.assertEqual(short_circuit_candidates(self.synthetic(boolean_result=tmp(99))),[])

    def test_unknown_instruction_has_no_candidate(self):
        data=self.synthetic()
        data['opcodes'][2]['decoded_opcode']=None
        self.assertEqual(short_circuit_candidates(data),[])

    def test_shape_needs_reaching_dataflow_proof(self):
        data=self.synthetic()
        # Another definition on the short-circuit path means provenance differs.
        data['opcodes'][0]['decoded_opcode']=0
        # Add a surprising transfer instead of the expected fallthrough region.
        data['opcodes'][2]['decoded_opcode']=42
        self.assertEqual(short_circuit_candidates(data),[])


class RealInputStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=produce(ROOT/'sample_inputs'/'fun_all.php',[],
                           ROOT/'zend_verified_dictionary.bin',
                           OPCODE_MAP)

    def test_unknown_199_repeats_and_is_not_promoted(self):
        rows=[r for r in self.report['unknown_and_disputed_contexts'] if r['key']=='1:199']
        self.assertEqual([(x['function'],x['index']) for x in rows],
                         [('out_price',65),('uc_rus',17)])
        self.assertEqual(rows[0]['fingerprint_sha256'],rows[1]['fingerprint_sha256'])
        self.assertTrue(all(r['opcode_confirmed'] is False for r in rows))
        self.assertTrue(any(x['encoded_key']=='1:199' and len(x['occurrences'])==2
                            for x in self.report['repeated_neighborhood_shapes']))

    def test_out_link_readonly_join_is_reproducible(self):
        joins=[item for group in self.report['possible_short_circuit_joins']
               if group['group']=='out_link' for item in group['join_candidates']]
        self.assertEqual([(x['jump_instruction'],x['boolean_instruction'],x['join_instruction'])
                           for x in joins],[(13,15,16)])
        self.assertTrue(all(x['emit_php_permitted'] is False for x in joins))

    def test_source_revision_links_are_only_hints(self):
        sources=[Path('/mnt/data/fun_all(1).php'),Path('/mnt/data/fun_all_.php')]
        if not all(s.is_file() for s in sources):
            self.skipTest('Optional user-owned reference sources not present')
        rep=produce(ROOT/'sample_inputs'/'fun_all.php',sources,
                    ROOT/'zend_verified_dictionary.bin',OPCODE_MAP)
        for item in [r for r in rep['unknown_and_disputed_contexts'] if r['key']=='1:199']:
            for file_hint in item['plaintext_function_hints'].values():
                self.assertTrue(file_hint['function_present'])
                self.assertTrue(file_hint['foreach_keyword'])
        self.assertFalse(rep['php_generated'])
        self.assertFalse(rep['semantic_equivalence_proven'])


if __name__=='__main__':unittest.main()
