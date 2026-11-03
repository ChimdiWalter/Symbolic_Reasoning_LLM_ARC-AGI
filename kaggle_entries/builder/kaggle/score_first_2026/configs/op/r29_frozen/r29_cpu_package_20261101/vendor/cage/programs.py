"""Typed closed programs, deterministic JSON tokens, pure interpretation."""
import copy
import json
import re
import math
import time
from .dependencies import E, M

SCHEMA = 'CAGE_PROGRAM_V1'

def wrap(body, kind='dsl'):
    result = {'schema': SCHEMA, 'kind': kind, 'body': copy.deepcopy(body)}
    result['program_sha256'] = E.digest(result)
    validate(result)
    return result

def validate(program):
    if type(program) is not dict or set(program) != {'schema', 'kind', 'body', 'program_sha256'}:
        raise E.Failure('CAGE_PROGRAM_SCHEMA')
    if program['schema'] != SCHEMA or program['kind'] not in ('dsl', 'conditional'):
        raise E.Failure('CAGE_PROGRAM_KIND')
    if E.digest({k: v for k, v in program.items() if k != 'program_sha256'}) != program['program_sha256']:
        raise E.Failure('CAGE_PROGRAM_HASH')
    if program['kind'] == 'dsl':
        E.validate_ast(program['body'])
    else:
        M.validate_model(program['body'])
    return program

def execute(program, grid, check=lambda: None, meter=None, caps=None):
    started=time.process_time()
    supplied=dict(caps or {})
    if any(k not in ('CPU_s','predicate_work','feature_cell_work') for k in supplied):
        raise E.Failure('UNKNOWN_PROGRAM_EXECUTION_CAP')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in supplied.values()):
        raise E.Failure('PROGRAM_EXECUTION_CAP_VALUE')
    def bounded():
        check()
        if time.process_time()-started>=supplied.get('CPU_s',2.0):
            raise E.Budget('PROGRAM_CPU_CAP_UNKNOWN')
    bounded()
    validate(program)
    if program['kind'] == 'dsl':
        return E.execute(program['body'], grid, check=bounded, meter=meter)
    Mlimits=dict(M.DEFAULT_CAPS,**supplied)
    Mlimits['CPU_s']-=time.process_time()-started
    if Mlimits['CPU_s']<=0:raise E.Budget('PROGRAM_CPU_CAP_UNKNOWN')
    meter={} if meter is None else meter
    for key in ('predicate_work','cell_work','feature_cell_work'):meter.setdefault(key,0)
    if meter.get('cell_limit') is not None:
        Mlimits['feature_cell_work']=min(Mlimits['feature_cell_work'],meter['cell_limit']-meter['cell_work'])
    if meter.get('predicate_limit') is not None:
        Mlimits['predicate_work']=min(Mlimits['predicate_work'],meter['predicate_limit']-meter['predicate_work'])
    if Mlimits['feature_cell_work']<=0 or Mlimits['predicate_work']<=0:
        raise E.Budget('PROGRAM_CONDITIONAL_SHARED_WORK_CAP_UNKNOWN')
    M._limits(Mlimits)
    # Preserve a conservative charge if caller cancellation interrupts M.predict.
    meter['cell_work']+=Mlimits['feature_cell_work']
    meter['feature_cell_work']+=Mlimits['feature_cell_work']
    meter['predicate_work']+=Mlimits['predicate_work']
    result = M.predict(program['body'], grid, caps=Mlimits, check=bounded)
    meter['cell_work']-=Mlimits['feature_cell_work']-result['cost']['feature_cell_work']
    meter['feature_cell_work']-=Mlimits['feature_cell_work']-result['cost']['feature_cell_work']
    meter['predicate_work']-=Mlimits['predicate_work']-result['cost']['predicate_work']
    if result['prediction'] is None:
        raise M.Abstention(result['reason'])
    return result['prediction']

def verify(program, train, check=lambda: None, meter=None, caps=None):
    E.valid_demos(train)
    started=time.process_time()
    limits=dict(caps or {})
    total=limits.get('CPU_s',2.0)
    meter={} if meter is None else meter
    for pair in train:
        remaining=total-(time.process_time()-started)
        if remaining<=0:raise E.Budget('PROGRAM_VERIFICATION_TOTAL_CPU_CAP_UNKNOWN')
        if execute(program,pair['input'],check=check,meter=meter,
                   caps=dict(limits,CPU_s=remaining))!=pair['output']:
            return False
    return True

def to_tokens(program):
    validate(program)
    # JSON lexical tokens preserve integers, parameter strings and typed syntax.
    return re.findall(r'"(?:\\.|[^"\\])*"|-?[0-9]+|true|false|null|[{}\[\],:]', E.canonical(program))

def from_tokens(tokens):
    if type(tokens) is not list or not tokens or len(tokens) > 100000 or any(type(t) is not str for t in tokens):
        raise E.Failure('CAGE_TOKEN_SCHEMA')
    if sum(map(len, tokens)) > 2000000:
        raise E.Failure('CAGE_TOKEN_LENGTH')
    program = json.loads(''.join(tokens))
    validate(program)
    if to_tokens(program) != tokens:
        raise E.Failure('NONCANONICAL_OR_AMBIGUOUS_TOKENS')
    return program
