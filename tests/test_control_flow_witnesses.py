"""Synthetic fail-closed CFG and finite path witness regressions.
No provided PHP or binary gets executed by this test module.
"""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.readonly_dataflow import read_definitions, analyze_file
from zend_decompiler.cfg import cfg_for_group, UNMODELED_CONTROL_FLOW
from zend_decompiler.serial_parser import FormatError


def unused(n=0, marker=0):
    return {'type':8, 'word0':n, 'word1':marker}


def tmp(n=0):
    return {'type':2, 'word0':n, 'word1':0}


def const(n=1):
    return {'type':1, 'constant':{'kind':'integer', 'value':n}}


def ins(i, code, *, op1=None, op2=None, result=None):
    return {'index':i, 'decoded_opcode':code,
            'op1':op1 if op1 is not None else unused(),
            'op2':op2 if op2 is not None else unused(),
            'result':result if result is not None else unused(),
            'line':i+1, 'extended_value':0}


class SoundCFGTests(unittest.TestCase):
    def test_exit_has_no_fallthrough_reaching_definition(self):
        ops=[ins(0,79,op1=const()),ins(1,52,result=tmp(),op1=const()),
             ins(2,40,op1=tmp()),ins(3,62,op1=const())]
        cfg=cfg_for_group('exit', {'opcodes':ops})
        self.assertEqual(cfg['reachable_blocks'],1)
        self.assertEqual(cfg['basic_blocks'][1]['reachable'],False)
        self.assertEqual(cfg['basic_blocks'][0]['successors'],[])
        report=read_definitions({'opcodes':ops})
        self.assertEqual(report['status'],'analyzed_syntactically')
        self.assertEqual(report['temporary_uses'],[])

    def test_unmodeled_native_control_flow_is_not_fallthrough(self):
        for native_id in sorted(UNMODELED_CONTROL_FLOW):
            with self.subTest(native_id=native_id):
                ops=[ins(0,native_id),ins(1,40,op1=tmp())]
                with self.assertRaisesRegex(FormatError,'Unmodeled control-flow'):
                    cfg_for_group('synthetic',{'opcodes':ops})
                report=read_definitions({'opcodes':ops})
                self.assertEqual(report['status'],'unsupported')
                self.assertEqual(report['unmodeled_control_flow'],
                                 [{'index':0,'native_opcode':native_id}])

    def test_unknown_jump_target_fails_closed_without_traceback(self):
        ops=[ins(0,42,op1=unused(999,1)),ins(1,40,op1=tmp())]
        report=read_definitions({'opcodes':ops})
        self.assertEqual(report['status'],'unsupported')
        self.assertIn('Out-of-range jump target',report['reason'])


class WitnessTests(unittest.TestCase):
    def test_branch_without_producer_preserves_undefined(self):
        ops=[ins(0,43,op1=const(),op2=unused(3,1)),
             ins(1,52,op1=const(),result=tmp()),
             ins(2,42,op1=unused(4,1)),
             ins(3,0),ins(4,40,op1=tmp()),ins(5,62,op1=const())]
        report=read_definitions({'opcodes':ops})
        row=report['temporary_uses'][0]
        self.assertEqual(row['reaching_definition_indices'],[-1,1])
        self.assertEqual(row['status'],'possibly_undefined')
        w=row['structural_path_witnesses']
        self.assertEqual(w['status'],'complete')
        self.assertEqual({x['definition_index']:x['instruction_path'] for x in w['witnesses']},
                         {-1:[0,3,4], 1:[0,1,2,4]})

    def test_loop_entry_path_exhibits_backedge(self):
        ops=[ins(0,40,op1=tmp()),ins(1,52,op1=const(),result=tmp()),
             ins(2,43,op1=const(),op2=unused(0,1)),ins(3,62,op1=const())]
        report=read_definitions({'opcodes':ops})
        row=report['temporary_uses'][0]
        self.assertEqual(row['reaching_definition_indices'],[-1,1])
        w=row['structural_path_witnesses']
        self.assertEqual(w['status'],'complete')
        self.assertEqual({x['definition_index']:x['instruction_path'] for x in w['witnesses']},
                         {-1:[0],1:[0,1,2,0]})

    def test_out_link_ambiguity_has_two_independent_cfg_witnesses(self):
        data=analyze_file(ROOT/'sample_inputs'/'fun_all.php',
                          ROOT/'zend_verified_dictionary.bin',
                          OPCODE_MAP)
        group=next(g for g in data['groups'] if g['group']=='out_link')
        row=next(r for r in group['temporary_uses']
                 if r['instruction_index']==16 and r['operand']=='op1')
        self.assertEqual(row['reaching_definition_indices'],[13,15])
        evidence=row['structural_path_witnesses']
        self.assertEqual(evidence['status'],'complete')
        self.assertEqual([w['definition_index'] for w in evidence['witnesses']],[13,15])
        self.assertTrue(all(w['instruction_path'][-1]==16 for w in evidence['witnesses']))
        self.assertTrue(all(w['definition_index'] in w['instruction_path'] for w in evidence['witnesses']))


class BoundedModelCheckTests(unittest.TestCase):
    def test_reaching_definitions_against_independent_instruction_graph(self):
        """300 generated *synthetic* 5-opcode programs, no PHP interpreter.

        The oracle is a direct state-space explorer, independent from the
        basic-block solver and its dominator/transfer implementation.
        """
        from collections import defaultdict, deque
        import random
        rng=random.Random(20271021)
        for case in range(300):
            count=5
            ops=[]
            for pc in range(count):
                opcode=rng.choice([0,40,52,42,43,62,79])
                if opcode==42:
                    op=ins(pc,opcode,op1=unused(rng.randrange(count+1),1))
                elif opcode==43:
                    op=ins(pc,opcode,op1=const(),op2=unused(rng.randrange(count+1),1))
                elif opcode==40:
                    op=ins(pc,opcode,op1=tmp())
                elif opcode==52:
                    op=ins(pc,opcode,op1=const(),result=tmp())
                else:
                    op=ins(pc,opcode)
                ops.append(op)
            oracle=defaultdict(set)
            todo=deque([(0,-1)])
            visited=set()
            while todo:
                pc,last=todo.popleft()
                if pc==count or (pc,last) in visited:continue
                visited.add((pc,last))
                op=ops[pc]
                if op['decoded_opcode']==40:oracle[pc].add(last)
                if op['decoded_opcode']==52:last=pc
                code=op['decoded_opcode']
                if code in (62,79):dest=[]
                elif code==42:dest=[op['op1']['word0']]
                elif code==43:dest=[pc+1,op['op2']['word0']]
                else:dest=[pc+1]
                for next_pc in dest:
                    todo.append((next_pc,last))
            rep=read_definitions({'opcodes':ops})
            self.assertEqual(rep['status'],'analyzed_syntactically',case)
            observed={r['instruction_index']:set(r['reaching_definition_indices'])
                      for r in rep['temporary_uses']}
            self.assertEqual(observed,dict(oracle),f'case {case}, opcodes {ops}')


if __name__=='__main__':
    unittest.main()
