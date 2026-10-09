def plan_git_lfs_pointer(records, policy):
    if not isinstance(records,list) or not isinstance(policy,dict) or policy.get('intent') not in ('checkout','stage_worktree'): raise ValueError("records and policy")
    seen,decisions=set(),[]
    for row in records:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('path'),str) or not isinstance(row.get('attr_lfs'),bool) or not isinstance(row.get('conflicted'),bool) or row.get('worktree_kind') not in ('pointer','content','missing') or not isinstance(row.get('pointer'),dict) or not isinstance(row.get('object_present'),bool): raise ValueError("record")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id']); ptr=row['pointer']
        if ptr.get('version')!='https://git-lfs.github.com/spec/v1' or not isinstance(ptr.get('oid'),str) or not ptr['oid'].startswith('sha256:') or len(ptr['oid'])!=71 or any(ch not in '0123456789abcdef' for ch in ptr['oid'][7:]) or not isinstance(ptr.get('size'),int) or ptr['size']<0: raise ValueError("pointer")
        if policy['intent']=='stage_worktree' and row['worktree_kind']=='content' and (not isinstance(row.get('worktree_oid'),str) or not row['worktree_oid'].startswith('sha256:') or len(row['worktree_oid'])!=71 or any(ch not in '0123456789abcdef' for ch in row['worktree_oid'][7:]) or not isinstance(row.get('worktree_size'),int) or row['worktree_size']<0): raise ValueError("worktree content identity")
        if row['conflicted']: action,reason='block','index_conflict'
        elif not row['attr_lfs']: action,reason='block','attribute_mismatch'
        elif row['object_present'] and row.get('object_oid')!=ptr['oid']: action,reason='block','object_oid_mismatch'
        elif row['object_present'] and row.get('object_size')!=ptr['size']: action,reason='block','object_size_mismatch'
        elif row['worktree_kind']=='content' and row.get('worktree_oid')==ptr['oid'] and row.get('worktree_size')==ptr['size']: action,reason='keep','hydrated_matches_pointer'
        elif row['worktree_kind'] in ('pointer','missing') and row['object_present'] and policy['intent']=='checkout': action,reason='hydrate','object_available'
        elif row['worktree_kind']=='content' and policy['intent']=='stage_worktree': action,reason='rewrite_pointer','stage_content_identity'
        elif not row['object_present']: action,reason='fetch_required','object_missing'
        else: action,reason='block','unreconciled_state'
        decisions.append({'id':row['id'],'path':row['path'],'action':action,'reason':reason,'pointer_oid':ptr['oid'],'pointer_size':ptr['size']})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions,'action_counts':{a:sum(x['action']==a for x in decisions) for a in ('keep','hydrate','rewrite_pointer','fetch_required','block')}}
