"""Domain-neutral typed trees, compiled rules, search accounting and anti-unification."""
import copy,hashlib,itertools,json,math
import domains as D

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def typ(domain):return 'Grid' if domain=='grid' else 'AttributedGraph'
def node(domain,op,**args):return {'op':op,'type':typ(domain),'args':args}
def inp(domain):return node(domain,'input')
def argument(domain,value):return {'type':'Axis' if domain=='grid' else 'Relation','value':value}
def children(ast):return [v for v in ast.get('args',{}).values() if isinstance(v,dict) and 'op'in v]
def count(ast):return (ast.get('op')!='input')+sum(count(v) for v in children(ast))
def walk(ast):
    yield ast
    for c in children(ast):yield from walk(c)

def substitute(value,bindings):
    if isinstance(value,dict):
        if 'var'in value:return copy.deepcopy(bindings[value['var']])
        return {k:substitute(v,bindings) for k,v in value.items()}
    if isinstance(value,list):return [substitute(v,bindings) for v in value]
    return value

def expand(ast,library):
    if ast['op']=='call':
        rule=next(r for r in library['rules'] if r['rule_id']==ast['args']['rule_id'])
        return expand(substitute(rule['body'],ast['args']['bindings']),library)
    out=copy.deepcopy(ast)
    for k,v in out['args'].items():
        if isinstance(v,dict) and 'op'in v:out['args'][k]=expand(v,library)
    return out

def execute(raw,ast,domain,representation,library=None):
    trace=[];spent=0
    try:
        if not D.valid(domain,raw):raise ValueError('TYPE_RAW_OBSERVATION')
        observation=D.normalize(domain,raw)
        ast=expand(ast,library or {'rules':[]})
        def run(a):
            nonlocal spent
            if not isinstance(a,dict) or set(a)!={'op','type','args'} or a['type']!=typ(domain):raise ValueError('TYPE_FAILURE')
            role=a['op'];args=a['args']
            if role=='input':
                if args:raise ValueError('TYPE_INPUT_ARGUMENT')
                return copy.deepcopy(observation)
            if role not in ('transform','combine','repeat','select','mark'):raise ValueError('LANGUAGE_FAILURE')
            expected={'left','right'} if role=='combine' else {'x','parameter'} if role=='transform' else {'x'}
            if set(args)!=expected:raise ValueError('TYPE_ARGUMENTS')
            values=[run(args[k]) for k in (('left','right') if role=='combine' else ('x',))]
            parameter=None
            if role=='transform':
                aarg=args['parameter'];required='Axis' if domain=='grid' else 'Relation'
                if set(aarg)!={'type','value'} or aarg['type']!=required:raise ValueError('TYPE_PARAMETER')
                parameter=aarg['value']
            spent+=1;out=D.primitive(domain,role,values,parameter,representation)
            if not D.valid(domain,out):raise ValueError('TYPE_OUTPUT')
            out=D.normalize(domain,out)
            trace.append({'operation':role,'input_sha256':digest(values),'output_sha256':digest(out),'primitive_execution':spent})
            return out
        output=run(ast)
        return output,{'status':'EXECUTED','primitive_executions':spent,'trace':trace,'raw_input_sha256':digest(raw)}
    except (ValueError,KeyError,StopIteration,TypeError) as error:
        return None,{'status':'FAILURE','failure_kind':str(error),'primitive_executions':spent,'trace':trace,'raw_input_sha256':digest(raw)}

def unary(domain,role,x,value=None):
    return node(domain,role,x=x,**({'parameter':argument(domain,value)} if role=='transform' else {}))
def base_universe(domain):
    i=inp(domain);params=('h','v') if domain=='grid' else ('r','s')
    descriptors=[('transform',p) for p in params]+[(r,None) for r in ('repeat','select','mark')]
    one=[unary(domain,r,i,p) for r,p in descriptors]
    programs=[i]+one
    programs += [unary(domain,r,x,p) for x in one for r,p in descriptors]
    programs += [node(domain,'combine',left=i,right=x) for x in one]
    programs += [node(domain,'combine',left=x,right=y) for x in one for y in one]
    return list({canonical(p):p for p in programs}.values())

def call(rule,x,p):return {'op':'call','type':rule['type'],'args':{'rule_id':rule['rule_id'],'bindings':{'x':x,'p0':p}}}
def extended_universe(domain,library):
    programs=base_universe(domain);i=inp(domain);params=('h','v') if domain=='grid' else ('r','s')
    for rule in library['rules']:
        calls=[call(rule,i,argument(domain,p)) for p in params]
        programs+=calls
        for x in calls:
            for p in params:programs.append(call(rule,x,argument(domain,p)))
            for role in ('mark','repeat','select'):programs.append(unary(domain,role,x))
            programs.append(node(domain,'combine',left=i,right=x))
        for p in params:
            programs.append(call(rule,unary(domain,'select',i),argument(domain,p)))
    return list({canonical(p):p for p in programs}.values())

def features(ast,domain,context,library):
    full=expand(ast,library);ops=[n['op'] for n in walk(full)]
    base=[1.,ops.count('transform')/4,ops.count('combine')/4,ops.count('select')/4,ops.count('mark')/4,ops.count('repeat')/4,count(full)/8]
    return base+[v*c for c in context for v in base]

def context(task):
    domain=task['domain'];rows=[]
    for pair in task['demos']:
        x,y=pair['input'],pair['output']
        if domain=='grid':a=sum(v!=0 for r in x for v in r);b=sum(v!=0 for r in y for v in r);n=len(x)*len(x[0])
        else:a=len(x['edges']);b=len(y['edges']);n=max(1,len(x['nodes'])**2)
        rows.append([(b-a)/max(1,a),float(b<a),min(a/max(1,n),1.)])
    return [sum(r[j] for r in rows)/len(rows) for j in range(3)]

def train_guide(tasks,solutions,universe,library,initial=None):
    weights=list(initial) if initial is not None else [0.]*28;updates=0
    for epoch in range(25):
        for task,solution in zip(tasks,solutions):
            if solution is None:continue
            subset=universe[:12]+[solution];fs=[features(a,task['domain'],context(task),library) for a in subset]
            scores=[sum(w*x for w,x in zip(weights,f)) for f in fs];m=max(scores);ex=[math.exp(min(30,s-m)) for s in scores];z=sum(ex)
            for j in range(len(weights)):
                gradient=sum(e/z*f[j] for e,f in zip(ex,fs))-fs[-1][j]
                weights[j]-=.15*gradient
            updates+=1
    return {'kind':'linear_conditional_softmax','weights':weights,'gradient_updates':updates,'training_task_count':len(tasks)}

def search(task,universe,library,guide=None,representation=None,revision=False,macro_prior=False,cap=24,primitive_cap=192):
    domain=task['domain'];default='mono4' if domain=='grid' else 'weak';alternative='color' if domain=='grid' else 'kind'
    representations=[representation or default]
    if revision:representations.append(alternative if representations[0]==default else default)
    ctx=context(task);order=list(range(len(universe)))
    if guide:
        def score(i):
            a=universe[i];f=features(a,domain,ctx,library)
            prior=sum(n['op']=='call' for n in walk(a))*.8 if macro_prior else 0.
            return (-sum(w*x for w,x in zip(guide['weights'],f))-prior,count(expand(a,library)),canonical(a))
        order.sort(key=score)
    else:order.sort(key=lambda i:(count(expand(universe[i],library)),canonical(universe[i])))
    receipts=[];checks=0;spent=0;selected=[];failures={}
    # Every representation shares the SAME total validation/execution budgets.
    per_view=max(1,cap//len(representations))
    revision_reason=None;used_representations=[]
    for stage_index in range(len(representations)):
        if stage_index==0:rep=representations[0];start_index=0
        else:
            distinct={digest(expand(r['AST'],library)) for r in receipts if r['exact']}
            revision_reason='NO_EXACT_FIT_IN_BOUNDED_PREFIX' if not distinct else 'MULTIPLE_DISTINCT_EXPANDED_FITS' if len(distinct)>1 else None
            rep=representations[1] if revision_reason else representations[0]
            start_index=0 if revision_reason else per_view
        used_representations.append(rep);local=0
        for i in order[start_index:]:
            a=universe[i];upper=count(expand(a,library))*len(task['demos'])
            if checks>=cap or spent+upper>primitive_cap:break
            if local>=per_view:break
            out=[execute(p['input'],a,domain,rep,library) for p in task['demos']]
            checks+=1;local+=1;spent+=sum(d['primitive_executions'] for y,d in out)
            exact=all(y==p['output'] for (y,d),p in zip(out,task['demos']))
            for y,d in out:
                if d['status']!='EXECUTED':failures[d['failure_kind']]=failures.get(d['failure_kind'],0)+1
            item={'AST':a,'representation':rep,'exact':exact,'validation':checks,'primitive_executions_cumulative':spent,
                  'execution_trace':out,'AST_sha256':digest(a)}
            receipts.append(item)
            if exact and len(selected)<2:selected.append(item)
    hypotheses={'search':'UNRESOLVED_BOUNDED_SEARCH','representation':'ALTERNATIVE_TESTED' if alternative in used_representations else 'ALTERNATIVE_NOT_TRIGGERED',
                 'language':'NO_ABSENCE_PROOF','composition':'BOUNDED_CANDIDATES_ONLY','evidence':'EXACT_FITS_MAY_BE_AMBIGUOUS'}
    if any(i['representation']==alternative for i in selected):hypotheses['representation']='ALTERNATIVE_EXACT_FIT_OBSERVED'
    return {'selected':selected,'receipts':receipts,'full_demo_validations':checks,'primitive_executions':spent,
            'failure_kinds':failures,'diagnoses':hypotheses,'revision_reason':revision_reason,'representations_executed':used_representations,'UNKNOWN':checks<len(universe)*len(representations)}

def antiunify(a,b,domain):
    bindings=[]
    def rec(x,y):
        if x==y:
            if isinstance(x,dict) and x.get('op')=='input':return {'var':'x','type':typ(domain)}
            return copy.deepcopy(x)
        if isinstance(x,dict) and isinstance(y,dict) and x.get('type')==y.get('type') and set(x)==set(y):
            if set(x)=={'type','value'}:
                name='p'+str(len(bindings));bindings.append((name,x['type']));return {'var':name,'type':x['type']}
            if x.get('op')!=y.get('op'):raise ValueError('STRUCTURE_DIFFERS')
            return {k:rec(x[k],y[k]) for k in x}
        if x!=y:raise ValueError('STRUCTURE_DIFFERS')
        return copy.deepcopy(x)
    body=rec(a,b)
    return body,[{'name':'x','type':typ(domain)}]+[{'name':n,'type':t} for n,t in bindings]

def match(pattern,value,bindings=None):
    bindings={} if bindings is None else bindings
    if isinstance(pattern,dict) and 'var'in pattern:
        name=pattern['var']
        if name in bindings and bindings[name]!=value:raise ValueError('INCONSISTENT_BINDING')
        bindings[name]=value;return bindings
    if isinstance(pattern,dict) and isinstance(value,dict) and set(pattern)==set(value):
        for k in pattern:match(pattern[k],value[k],bindings)
    elif pattern!=value:raise ValueError('NO_MATCH')
    return bindings

def mdl_bits(ast):
    if 'var'in ast:return 4
    if set(ast)=={'type','value'}:return 4
    if ast.get('op')=='input':return 1
    if ast.get('op')=='call':return 8+sum(mdl_bits(v) for v in ast['args']['bindings'].values())
    return 16+sum(mdl_bits(v) for v in ast.get('args',{}).values() if isinstance(v,dict))

def discover(domain,tasks,solutions):
    candidates={};rejected=[]
    for a,b in itertools.combinations([p for p in solutions if p is not None],2):
        try:
            body,params=antiunify(a,b,domain)
            if len(params)!=2 or count(body)<2:continue
            candidates[digest(body)]=(body,params)
        except (ValueError,KeyError):pass
    for key,(body,params) in candidates.items():
        supports=[]
        for task,p in zip(tasks,solutions):
            if p is None:continue
            try:supports.append((task,p,match(body,p)))
            except ValueError:pass
        rule={'rule_id':'L0','version':1,'domain':domain,'type':typ(domain),'params':params,'body':body,
              'preconditions':'Typed domain inputs and every underlying primitive precondition; partial failures propagate.',
              'provenance':{'search_solved_tasks':[t['id'] for t,p,b in supports],'generator_target_AST_access':False}}
        library={'schema':1,'version':1,'rules':[rule]};verification=[]
        for task,p,bindings in supports:
            compiled={'op':'call','type':typ(domain),'args':{'rule_id':'L0','bindings':bindings}}
            for other in tasks:
                for pair in other['demos']:
                    left=execute(pair['input'],compiled,domain,'mono4' if domain=='grid' else 'weak',library)
                    right=execute(pair['input'],p,domain,'mono4' if domain=='grid' else 'weak')
                    if left[0]!=right[0] or left[1]['status']!=right[1]['status']:raise ValueError('EXPANSION_REGRESSION')
                    verification.append({'input_sha256':digest(pair['input']),'compiled_sha256':digest(left[0]),'expanded_sha256':digest(right[0]),
                                         'primitive_executions':left[1]['primitive_executions']+right[1]['primitive_executions']})
        original=sum(mdl_bits(p) for t,p,b in supports);definition=16+4*len(params)+mdl_bits(body)
        rewritten=sum(8+sum(mdl_bits(v) for v in b.values()) for t,p,b in supports)
        net=original-definition-rewritten
        rule.update({'MDL':{'coding':'16bit primitive op,8bit librarycall,4bit typed arg/variable,1bit input; definition16bit header+4bit/param+body. Metadata/provenance bytes separately reported.',
                            'original_bits':original,'definition_bits':definition,'rewritten_bits':rewritten,'net_saving_bits':net},
                     'expansion_tests':verification,'known_limitations':'Finite all-training-context equality, not universal equivalence or held-task correctness.'})
        if len(supports)>=2 and net>0:return library,rejected
        rejected.append({'candidate':key,'support_tasks':len(supports),'net_saving_bits':net})
    return {'schema':1,'version':0,'rules':[]},rejected

def token_envelope(kind,payload):return {'schema':'execution_grounded_tokens_v1','kind':kind,'payload':payload,
    'model_tokens':'UTF8 JSON bytes, not an LLM tokenizer or pretrained model','semantic_operations':'Interpreter op IDs with typed contracts',
    'library_rules':'Versioned compiled callable definitions; adding one does not alter model tokenizer'}
