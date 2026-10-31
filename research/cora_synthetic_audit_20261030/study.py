"""One frozen causal-prior audit. All imports and computations run under slot."""
import json
import time
import engine as E
import invented as I


def prefix_fingerprint(rows):
    return E.digest([{k:r[k] for k in ('expanded_AST_sha256','view','exact','output_sha256s','statuses')} for r in rows])

def main(here, save, sha, check):
    begun = time.process_time(); tasks = I.training(); base = E.rows_for_base(); solutions = []; training = []
    for task in tasks:
        check(); result = E.run_search(task, base, [0.] * 28, check, cap=48, primitive_cap=384, cpu_cap=.15)
        fitting = [r for r in result['rows'] if r['exact']]
        solutions.append(base[fitting[0]['index']]['expanded'] if fitting else None)
        training.append({'id':task['id'],'result':result,'verified_solution':solutions[-1]})
    check(); library, rejected = E.C.discover('grid', tasks, solutions)
    if not library['rules']:
        stopped={'status':'NO_LEARNED_RULE_STOPPED_BEFORE_HELD_GENERATION','library':library,'rejected_rules':rejected,
            'training_results':training,'verified_training_solutions':sum(s is not None for s in solutions),
            'held_demo_values_generated':0,'held_query_inputs_generated':0,'held_query_targets_generated':0,
            'induction_CPU_s':time.process_time()-begun}
        check();save('LIBRARY_GUIDE_FROZEN.json',stopped)
        report={'status':'COMPLETE_NEGATIVE_NO_LEARNED_RULE','reason':'NO_LEARNED_RULE','full_denominator':8,
            'UNKNOWN_held_tasks':8,'accuracy_measured':False,'results':None,'library_rules':0,
            'held_demos_queries_targets_generated':0,'real_ARC_gain_established':False,
            'classification':'DEVELOPMENT_SYNTHETIC_INDUCTION_NEGATIVE_NO_HELD_CLAIM'}
        save('EXPERIMENT_RESULTS.json',report);check();return report
    check(); guide = E.C.train_guide(tasks, solutions, [r['expanded'] for r in base], {'rules': []})
    check(); universe, universe_receipt = E.freeze_universe(library, check)
    training_receipt = {'status':'AUTOMATIC_SEARCH_AU_COMPILE_LIBRARY_GUIDE_FROZEN_BEFORE_HELD_DEMOS',
        'library':library,'guide':guide,'rejected_rules':rejected,'training_results':training,
        'verified_training_solutions':sum(s is not None for s in solutions),
        'search_validations':sum(t['result']['validations'] for t in training),
        'search_primitives':sum(t['result']['primitive_executions'] for t in training),
        'compiled_expansion_primitive_executions':sum(x['primitive_executions'] for r in library['rules'] for x in r['expansion_tests']),
        'induction_CPU_s':time.process_time()-begun,'held_demo_values_generated':0,'held_query_inputs_generated':0,'held_targets_generated':0}
    check(); save('LIBRARY_GUIDE_FROZEN.json',training_receipt)
    save('COMMON_UNIVERSE_FROZEN.json',{'status':'FROZEN_BEFORE_HELD_DEMOS','rows':universe,'receipt':universe_receipt,
        'library_guide_sha256':sha(here/'LIBRARY_GUIDE_FROZEN.json'),'held_demo_values_generated':0})
    check(); held = I.retained_tasks(); evidence = {}; shared_prefix = {}
    for task in held:
        check(); trace = E.run_search(task,universe,guide['weights'],check,cap=12)
        shared_prefix[task['id']] = trace
        evidence[task['id']] = E.failure_payload(trace)
        evidence[task['id']]['prefix_fingerprint'] = prefix_fingerprint(trace['rows'])
    all8_shared_prefixes_exact12=all(len(t['rows'])==12 for t in shared_prefix.values())
    check(); save('ALL8_FAILURE_PREFIXES_FROZEN.json',{'status':'ALL8_FROZEN_BEFORE_CYCLIC_ROUTING',
        'all8_shared_prefixes_exact12':all8_shared_prefixes_exact12,
        'prefixes':shared_prefix,'payloads':evidence,'query_inputs_generated':0,'query_targets_generated':0})
    evidence_sha = sha(here/'ALL8_FAILURE_PREFIXES_FROZEN.json')
    all_traces = {}; selected = {}; matches = {}; own_prefix_replay={}; id_order = [t['id'] for t in held]
    for position, task in enumerate(held):
        check(); tid = task['id']; traces = {}
        for name, lam, shuffled in [('lambda0',0.,False),('lambda_plus',.8,False),('lambda_minus',-.8,False),('expanded_control',0.,False),('shuffled_call_prior',.8,True)]:
            check(); traces[name] = E.run_search(task,universe,guide['weights'],check,lam=lam,shuffled=shuffled)
        if traces['lambda0']['order'] != traces['expanded_control']['order']:
            raise AssertionError('LAMBDA0_EXPANDED_ORDER_MISMATCH')
        traces['base_reference'] = E.run_search(task,base,guide['weights'],check)
        borrowed_id = id_order[(position-1)%len(id_order)]
        borrowed = {'source_task':borrowed_id,**evidence[borrowed_id], 'all8_evidence_freeze_sha256':evidence_sha}
        for name, action in [('failure_authentic','authentic'),('failure_blind','blind'),('failure_shuffled','shuffled'),('failure_static','static'),('failure_extra_search','extra_search')]:
            check(); traces[name] = E.run_search(task,universe,guide['weights'],check,lam=0.,action=action,payload=borrowed)
            # Own prefix must replay shared semantic evidence; timing may cap a
            # replay earlier, so compare exact common observed prefix only.
            count = min(12,len(traces[name]['rows']),len(shared_prefix[tid]['rows']))
            identical=prefix_fingerprint(traces[name]['rows'][:count])==prefix_fingerprint(shared_prefix[tid]['rows'][:count])
            if not identical:raise AssertionError('FAILURE_ARM_OWN_PREFIX_REPLAY_MISMATCH')
            own_prefix_replay.setdefault(tid,{})[name]={'common_observed_prefix':count,'common_prefix_identical':identical,
                'own_and_shared_exact12':len(traces[name]['rows'])>=12 and len(shared_prefix[tid]['rows'])==12}
        primary_match = E.matched_prefix({name:traces[name] for name in E.PRIMARY})
        failure_match = E.matched_prefix({name:traces[name] for name in E.FAILURE})
        matches[tid] = {'primary':primary_match,'failure':failure_match,
            'failure_postintervention_identifiable':failure_match['common_validation_prefix_length']>12,
            'authentic_payload':evidence[tid],'shuffled_payload_source':borrowed_id}
        selected[tid] = {mode:{} for mode in ('raw_common_caps','matched_common_prefix')}
        for name, trace in traces.items():
            rows = base if name=='base_reference' else universe
            raw = E.choices(trace,rows)
            if name in E.PRIMARY: limit=primary_match['common_validation_prefix_length']
            elif name in E.FAILURE: limit=failure_match['common_validation_prefix_length']
            else: limit=None
            selected[tid]['raw_common_caps'][name] = raw
            selected[tid]['matched_common_prefix'][name] = E.choices(trace,rows,limit)
        if selected[tid]['matched_common_prefix']['lambda0'] != selected[tid]['matched_common_prefix']['expanded_control']:
            raise AssertionError('LAMBDA0_EXPANDED_JOINT_PREFIX_SELECTION_MISMATCH')
        all_traces[tid] = traces
    check(); save('ALL_SELECTED_AST_FROZEN.json',{'status':'ALL8_ALL11_BOTH_MODES_FROZEN_BEFORE_QUERY_INPUTS',
        'selected':selected,'cost_matches':matches,'library_guide_sha256':sha(here/'LIBRARY_GUIDE_FROZEN.json'),
        'universe_sha256':sha(here/'COMMON_UNIVERSE_FROZEN.json'),'failure_evidence_sha256':evidence_sha,
        'held_query_inputs_generated':0,'held_query_targets_generated':0})
    selected_sha=sha(here/'ALL_SELECTED_AST_FROZEN.json'); predictions={}; queries={}; parity=[]; query_primitive=0
    for spec,task in zip(I.SPECS,held):
        check();tid=task['id'];raw=I.input_grid(spec);queries[tid]=raw;predictions[tid]={}
        for mode,arms in selected[tid].items():
            predictions[tid][mode]={}
            for name,choices in arms.items():
                outputs=[]
                for choice_index,choice in enumerate(choices):
                    check();expanded,er=E.C.execute(raw,choice['expanded'],'grid',choice['view'])
                    compiled,cr=E.C.execute(raw,choice['representative'],'grid',choice['view'],library)
                    query_primitive+=er['primitive_executions']+cr['primitive_executions']
                    if compiled!=expanded or cr['status']!=er['status']:
                        raise AssertionError('ACTUAL_SELECTED_COMPILED_EXPANDED_REUSE_MISMATCH')
                    parity.append({'task':tid,'mode':mode,'arm':name,'selected_choice_index':choice_index,'AST_sha256':choice['expanded_AST_sha256'],
                        'legacy_calls':choice['legacy_call_feature'],'true_recursive_calls':choice['true_recursive_call_count'],
                        'compiled_output_sha256':E.digest(compiled),'expanded_output_sha256':E.digest(expanded),
                        'compiled_status':cr['status'],'expanded_status':er['status'],
                        'compiled_failure_kind':cr.get('failure_kind'),'expanded_failure_kind':er.get('failure_kind')})
                    outputs.append(expanded)
                predictions[tid][mode][name]=outputs if outputs else [raw]
    for tid in predictions:
        if predictions[tid]['matched_common_prefix']['lambda0']!=predictions[tid]['matched_common_prefix']['expanded_control']:
            raise AssertionError('LAMBDA0_EXPANDED_PREDICTION_MISMATCH')
    check();save('ALL_PREDICTIONS_FROZEN.json',{'status':'ALL_OUTPUTS_FROZEN_BEFORE_QUERY_TARGETS','queries':queries,
        'predictions':predictions,'selected_AST_sha256':selected_sha,'compiled_expanded_parity':parity,
        'query_render_and_parity_primitives':query_primitive,'held_query_targets_generated':0})
    prediction_sha=sha(here/'ALL_PREDICTIONS_FROZEN.json');check()
    # First query target calls. Independent declarative generator cannot access
    # selected programs/library and is never used for macro discovery.
    truth={task['id']:I.target(queries[task['id']],spec['family'],spec['parameter']) for spec,task in zip(I.SPECS,held)}
    check();save('SYNTHETIC_TARGETS_AFTER_PREDICTION_FREEZE.json',{'prediction_sha256':prediction_sha,'targets':truth})
    raw_identity={tid:selected[tid]['raw_common_caps']['lambda0']==selected[tid]['raw_common_caps']['expanded_control'] and predictions[tid]['raw_common_caps']['lambda0']==predictions[tid]['raw_common_caps']['expanded_control'] for tid in predictions}
    query_status_counts={mode:{name:{'expanded_EXECUTED':0,'expanded_FAILURE':0,'compiled_EXECUTED':0,'compiled_FAILURE':0} for name in E.ARMS} for mode in ('raw_common_caps','matched_common_prefix')}
    query_invalid_tasks={mode:{name:set() for name in E.ARMS} for mode in ('raw_common_caps','matched_common_prefix')}
    correct_macro_tasks={mode:{name:set() for name in E.ARMS} for mode in ('raw_common_caps','matched_common_prefix')}
    for replay in parity:
        tid,mode,name,index=replay['task'],replay['mode'],replay['arm'],replay['selected_choice_index']
        for renderer in ('expanded','compiled'):
            query_status_counts[mode][name][renderer+'_'+replay[renderer+'_status']]+=1
        if replay['expanded_status']!='EXECUTED' or replay['compiled_status']!='EXECUTED':
            query_invalid_tasks[mode][name].add(tid)
        if replay['true_recursive_calls']>0 and replay['expanded_status']=='EXECUTED' and predictions[tid][mode][name][index]==truth[tid]:
            correct_macro_tasks[mode][name].add(tid)
    results={}
    for mode in ('raw_common_caps','matched_common_prefix'):
        per={name:{tid:any(y==truth[tid] for y in predictions[tid][mode][name]) for tid in predictions} for name in E.ARMS}
        results[mode]={name:{'hits':sum(per[name].values()),'denominator':8,
            'correct_task_ids':[tid for tid,v in per[name].items() if v],
            'verified_program_hits':sum(per[name][tid] and bool(selected[tid][mode][name]) for tid in per[name]),
            'COPY_fallback_hits':sum(per[name][tid] and not selected[tid][mode][name] for tid in per[name]),
            'correct_learned_call_task_ids':sorted(correct_macro_tasks[mode][name]),
            'correct_learned_call_tasks':len(correct_macro_tasks[mode][name]),
            'gain_vs_lambda0':[tid for tid in per[name] if per[name][tid] and not per['lambda0'][tid]],
            'loss_vs_lambda0':[tid for tid in per[name] if per['lambda0'][tid] and not per[name][tid]]} for name in E.ARMS}
    action_records={tid:{n:{'action_executed':all_traces[tid][n]['action_executed'],
        'alternate_view':all_traces[tid][n]['alternate_view']} for n in E.FAILURE} for tid in all_traces}
    authentic_actions={str(v['failure_authentic']['alternate_view']) for v in action_records.values()}
    authentic_triggers={evidence[tid]['alternate'] for tid in evidence}
    all_own_prefixes_exact12=all(v['own_and_shared_exact12'] for arms in own_prefix_replay.values() for v in arms.values())
    unknown={name:sum(all_traces[tid][name]['UNKNOWN'] for tid in all_traces) for name in E.ARMS}
    report={'status':'COMPLETE_DEVELOPMENT_SYNTHETIC_CAUSAL_FALSIFIER','results':results,
        'library_rules':len(library['rules']),'library_sha256':E.digest(library),'universe':universe_receipt,
        'lambda0_expanded_order_identical':True,
        'lambda0_expanded_MATCHED_selected_predictions_identical':True,
        'lambda0_expanded_RAW_selected_predictions_identical':all(raw_identity.values()),
        'lambda0_expanded_RAW_timing_or_cap_artifact_task_ids':[tid for tid,identical in raw_identity.items() if not identical],
        'all_failure_arm_lambdas_zero':all(all_traces[t][n]['lambda']==0 for t in all_traces for n in E.FAILURE),
        'all8_shared_prefixes_exact12':all8_shared_prefixes_exact12,
        'all_failure_arms_own_prefixes_exact12':all_own_prefixes_exact12,
        'own_prefix_replay_receipts':own_prefix_replay,
        'failure_actions':action_records,'failure_trigger_variation':len(authentic_triggers)>1,
        'actual_authentic_action_variation_including_unexecuted':len(authentic_actions)>1,
        'secondary_identifiability':'INCOMPLETE_SHARED_EVIDENCE_OR_REPLAY_NOT_IDENTIFIABLE' if not(all8_shared_prefixes_exact12 and all_own_prefixes_exact12) else
            'NON_IDENTIFIABLE_CONSTANT_TRIGGER' if len(authentic_triggers)<=1 else
            'NO_POSTINTERVENTION_MATCHED_PREFIX' if not any(v['failure_postintervention_identifiable'] for v in matches.values()) else 'CHECK_PAIRED_RESULTS',
        'secondary_postintervention_matched_task_ids':[tid for tid,m in matches.items() if m['failure_postintervention_identifiable']],
        'shuffled_prior_informative':universe_receipt['effective_shuffled_label_changes']>0,
        'UNKNOWN_counts':unknown,'full_denominator':8,'query_render_and_parity_primitives':query_primitive,
        'selected_query_execution_status_counts_by_mode_arm':query_status_counts,
        'selected_query_invalid_or_undefined_task_ids_by_mode_arm':{m:{n:sorted(ids) for n,ids in arms.items()} for m,arms in query_invalid_tasks.items()},
        'selected_query_invalid_or_undefined_replay_count':sum(p['expanded_status']!='EXECUTED' or p['compiled_status']!='EXECUTED' for p in parity),
        'correct_learned_call_task_ids_by_mode_arm':{m:{n:sorted(ids) for n,ids in arms.items()} for m,arms in correct_macro_tasks.items()},
        'actual_selected_compiled_replays':len(parity),'selected_replays_with_true_learned_calls':sum(p['true_recursive_calls']>0 for p in parity),
        'no_new_primitive_or_expanded_behavior':True,'real_ARC_gain_established':False,
        'classification':'DEVELOPMENT_SYNTHETIC_NEW_COMPOSITIONS_NOT_INDEPENDENT_CONFIRMATION',
        'cost_matching':matches,'all_outputs_before_query_truth':True,
        'search_actual_CPU_s':{n:sum(all_traces[t][n]['actual_CPU_s'] for t in all_traces) for n in E.ARMS},
        'shared_failure_acquisition_CPU_s':sum(v['actual_CPU_s'] for v in shared_prefix.values()),
        'all_training_ranking_validation_render_serialization_under_guard':True,
        'limitation':'Authored schemas/views/generators and callprior remain engineered. This isolates schedule attribution, not novel abstraction algorithm, expressivity or universal capability growth.'}
    check();save('SEARCH_TRACES.json',all_traces);save('EXPERIMENT_RESULTS.json',report);check()
    return report
