"""Independent synthetic domain semantics. No target ASTs/traces are exported."""
import copy,random


def grid_input(seed,structured=False):
    rng=random.Random(seed);h,w=rng.randint(5,8),rng.randint(5,8)
    g=[[0]*w for _ in range(h)]
    if structured:
        for r,c in [(0,0),(0,2),(2,0),(2,2)]:g[r][c]=1
        g[h-1][w-1]=g[h-1][w-2]=2
    else:
        for _ in range(4):g[rng.randrange(h//2)][rng.randrange(w//2)]=1
        g[1][min(2,w-1)]=1
    return g


def graph_input(seed,structured=False):
    rng=random.Random(seed);n=rng.randint(5,8)
    nodes=[{'id':str(i),'kind':'A' if i%2==0 else 'B','flag':False} for i in range(n)]
    edges={(str(i),str((i+1)%n),'r' if i%2==0 else 's') for i in range(n-1)}
    edges|={(str(rng.randrange(n)),str(rng.randrange(n)),rng.choice(['r','s'])) for _ in range(2)}
    if structured:edges={('0','1','r'),('1','3','s')}
    return {'nodes':nodes,'edges':[list(e) for e in sorted(edges)]}


def groups(domain,raw,representation):
    if domain=='grid':
        cells={(r,c) for r,row in enumerate(raw) for c,v in enumerate(row) if v}
        if representation=='color':return [{p for p in cells if raw[p[0]][p[1]]==v} for v in sorted({raw[r][c] for r,c in cells})]
        if representation!='mono4':raise ValueError('REPRESENTATION_UNKNOWN')
        out=[]
        while cells:
            p=min(cells);cells.remove(p);seen={p};todo=[p]
            while todo:
                r,c=todo.pop()
                for q in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):
                    if q in cells and raw[q[0]][q[1]]==raw[p[0]][p[1]]:cells.remove(q);seen.add(q);todo.append(q)
            out.append(seen)
        return out
    ids={n['id'] for n in raw['nodes']}
    if representation=='kind':return [{n['id'] for n in raw['nodes'] if n['kind']==k} for k in sorted({n['kind'] for n in raw['nodes']})]
    if representation!='weak':raise ValueError('REPRESENTATION_UNKNOWN')
    adjacency={v:set() for v in ids}
    for a,b,r in raw['edges']:adjacency[a].add(b);adjacency[b].add(a)
    out=[]
    while ids:
        p=min(ids);ids.remove(p);seen={p};todo=[p]
        while todo:
            for q in adjacency[todo.pop()]&ids:ids.remove(q);seen.add(q);todo.append(q)
        out.append(seen)
    return out


def primitive(domain,role,values,arg,representation):
    if domain=='grid':
        g=values[0];h,w=len(g),len(g[0])
        if role=='transform':
            if arg not in ('h','v'):raise ValueError('TYPE_AXIS')
            return [row[::-1] for row in g] if arg=='h' else g[::-1]
        if role=='combine':
            b=values[1]
            if (h,w)!=(len(b),len(b[0])):raise ValueError('SHAPE_PRECONDITION')
            if any(g[r][c] and b[r][c] and g[r][c]!=b[r][c] for r in range(h) for c in range(w)):raise ValueError('OVERLAY_CONFLICT')
            return [[g[r][c] or b[r][c] for c in range(w)] for r in range(h)]
        if role=='repeat':
            if 2*max(h,w)>24:raise ValueError('BOUNDS_PRECONDITION')
            return [row*2 for row in g]*2
        if role=='mark':return [[2 if c else 0 for c in row] for row in g]
        if role=='select':
            gs=groups(domain,g,representation);best=max(map(len,gs),default=0);chosen=[s for s in gs if len(s)==best]
            if len(chosen)!=1:raise ValueError('AMBIGUOUS_SELECTION')
            return [[g[r][c] if (r,c) in chosen[0] else 0 for c in range(w)] for r in range(h)]
    else:
        g=copy.deepcopy(values[0]);ids={n['id'] for n in g['nodes']}
        if role=='transform':
            if arg not in ('r','s'):raise ValueError('TYPE_RELATION')
            g['edges']=sorted([b,a,r] if r==arg else [a,b,r] for a,b,r in g['edges']);return g
        if role=='combine':
            b=values[1]
            if g['nodes']!=b['nodes']:raise ValueError('NODE_INTERFACE_PRECONDITION')
            g['edges']=[list(e) for e in sorted({tuple(e) for e in g['edges']+b['edges']})];return g
        if role=='repeat':
            if len(ids)*2>24:raise ValueError('BOUNDS_PRECONDITION')
            used=set(ids);renaming={}
            for ident in sorted(ids):
                fresh=ident+'x'
                while fresh in used:fresh+='x'
                used.add(fresh);renaming[ident]=fresh
            g['nodes'] += [dict(n,id=renaming[n['id']]) for n in g['nodes']]
            g['edges'] += [[renaming[a],renaming[b],r] for a,b,r in g['edges']];return normalize(domain,g)
        if role=='mark':
            for n in g['nodes']:
                if n['kind']=='A':n['flag']=True
            return g
        if role=='select':
            gs=groups(domain,g,representation);best=max(map(len,gs),default=0);chosen=[s for s in gs if len(s)==best]
            if len(chosen)!=1:raise ValueError('AMBIGUOUS_SELECTION')
            keep=chosen[0];g['nodes']=[n for n in g['nodes'] if n['id'] in keep];g['edges']=[e for e in g['edges'] if e[0] in keep and e[1] in keep];return g
    raise ValueError('LANGUAGE_UNKNOWN_OPERATION')


def target(domain,raw,family,parameter):
    """Independent specification code: never returns a program or DSL trace."""
    if domain=='grid':
        g=copy.deepcopy(raw)
        if family=='selection_completion':
            counts={c:sum(row.count(c) for row in g) for c in (1,2)};c=max(counts,key=counts.get)
            g=[[v if v==c else 0 for v in row] for row in g]
        axes=['h','v'] if family=='double_completion' else [parameter]
        for axis in axes:
            h,w=len(g),len(g[0]);old=copy.deepcopy(g)
            for r in range(h):
                for c in range(w):g[r][c]=old[r][c] or old[r if axis=='h' else h-1-r][w-1-c if axis=='h' else c]
        if family=='completion_mark':g=[[2 if v else 0 for v in row] for row in g]
        return g
    g=copy.deepcopy(raw)
    if family=='selection_completion':
        counts={k:sum(n['kind']==k for n in g['nodes']) for k in ('A','B')};k=max(counts,key=counts.get)
        keep={n['id'] for n in g['nodes'] if n['kind']==k};g['nodes']=[n for n in g['nodes'] if n['id'] in keep];g['edges']=[e for e in g['edges'] if e[0] in keep and e[1] in keep]
    relations=['r','s'] if family=='double_completion' else [parameter]
    es={tuple(e) for e in g['edges']}
    for relation in relations:es|={(b,a,r) for a,b,r in list(es) if r==relation}
    g['edges']=[list(e) for e in sorted(es)]
    if family=='completion_mark':
        for n in g['nodes']:
            if n['kind']=='A':n['flag']=True
    return g


def make_task(domain,index,family,parameter):
    generator=grid_input if domain=='grid' else graph_input
    seed=(10000 if domain=='grid' else 90000)+index*31
    demos=[]
    for j in range(2):
        raw=generator(seed+j,family=='selection_completion');demos.append({'input':raw,'output':target(domain,raw,family,parameter)})
    return {'id':domain+'_'+str(index),'domain':domain,'demos':demos}


def training(domain):
    params=('h','v') if domain=='grid' else ('r','s')
    return [make_task(domain,i,'single_completion',params[i%2]) for i in range(12)]


def held_specs(domain):
    params=('h','v') if domain=='grid' else ('r','s')
    return [{'domain':domain,'index':100+i,'family':family,'parameter':params[i%2]} for i,family in enumerate(
            ['double_completion','double_completion','completion_mark','completion_mark','selection_completion','selection_completion'])]


def query_input(spec):
    generator=grid_input if spec['domain']=='grid' else graph_input
    return generator((70000 if spec['domain']=='grid' else 170000)+spec['index']*17,spec['family']=='selection_completion')


def valid(domain,raw):
    if domain=='grid':
        return (type(raw)is list and 0<len(raw)<=24 and type(raw[0])is list and 0<len(raw[0])<=24 and
          all(type(row)is list and len(row)==len(raw[0]) and all(type(v)is int and 0<=v<=9 for v in row) for row in raw))
    if type(raw)is not dict or set(raw)!={'nodes','edges'} or type(raw['nodes'])is not list or not raw['nodes'] or type(raw['edges'])is not list:return False
    ns=raw['nodes']
    if any(type(n)is not dict or set(n)!={'id','kind','flag'} or type(n['id'])is not str or n['kind'] not in ('A','B') or type(n['flag'])is not bool for n in ns):return False
    ids={n['id'] for n in ns}
    if len(ids)!=len(ns):return False
    es=raw['edges']
    if any(type(e)is not list or len(e)!=3 or e[0] not in ids or e[1] not in ids or e[2] not in ('r','s') for e in es):return False
    return len(set(map(tuple,es)))==len(es)


def normalize(domain,raw):
    if domain=='grid':return copy.deepcopy(raw)
    return {'nodes':sorted(copy.deepcopy(raw['nodes']),key=lambda n:n['id']),
            'edges':[list(e) for e in sorted(map(tuple,raw['edges']))]}
