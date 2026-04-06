#!/usr/bin/env python3
"""
Span-based Coreference Resolution Evaluator v2
- XML에서 mention + character offset 추출
- 문맥 기반 mention 매칭
- MUC, B³, CEAFϕ4 정식 산출
- 매칭 검증 리포트 포함
"""
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher


# ============================================================
# 1. XML → mention 추출 (character offset + context)
# ============================================================

def extract_mentions_with_context(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    body_match = re.search(r'<body>(.*?)</body>', content, re.DOTALL)
    if not body_match:
        body_match = re.search(r'<text>(.*?)</text>', content, re.DOTALL)
    if not body_match:
        raise ValueError(f"No <body> or <text> in {filepath}")
    body_xml = body_match.group(1)
    mentions = []
    char_pos = 0; i = 0; tag_stack = []; plain_chars = []
    while i < len(body_xml):
        if body_xml[i] == '<':
            tag_end = body_xml.index('>', i)
            tag_full = body_xml[i:tag_end+1]
            open_match = re.match(r'<(rs|persName)\s[^>]*ref="([^"]*)"[^>]*>', tag_full)
            if open_match:
                tag_stack.append({
                    'tag': open_match.group(1),
                    'ref': open_match.group(2).strip().replace('#','').replace(' ','_'),
                    'start': char_pos, 'text_parts': []
                })
                i = tag_end + 1; continue
            close_match = re.match(r'</(rs|persName)>', tag_full)
            if close_match and tag_stack and tag_stack[-1]['tag'] == close_match.group(1):
                info = tag_stack.pop()
                mt = re.sub(r'<[^>]+>', '', ''.join(info['text_parts'])).strip()
                if mt:
                    mentions.append({
                        'ref': info['ref'], 'text': mt,
                        'start': info['start'], 'end': char_pos
                    })
                i = tag_end + 1; continue
            i = tag_end + 1; continue
        else:
            plain_chars.append(body_xml[i])
            for frame in tag_stack:
                frame['text_parts'].append(body_xml[i])
            char_pos += 1; i += 1
    plain_text = ''.join(plain_chars)
    for m in mentions:
        cs = max(0, m['start']-15)
        ce = min(len(plain_text), m['end']+15)
        m['context'] = plain_text[cs:ce]
    return mentions, plain_text


# ============================================================
# 2. 문맥 기반 mention 매칭
# ============================================================

def match_mentions_by_context(gold_mentions, sys_mentions, gold_text, sys_text):
    matched = []; used_sys = set()
    for gi, gm in enumerate(gold_mentions):
        best_score = 0; best_si = -1
        for si, sm in enumerate(sys_mentions):
            if si in used_sys: continue
            if gm['text'] == sm['text']:
                ctx_score = SequenceMatcher(None, gm['context'], sm['context']).ratio()
                score = 1.0 + ctx_score
            elif gm['text'] in sm['text'] or sm['text'] in gm['text']:
                ctx_score = SequenceMatcher(None, gm['context'], sm['context']).ratio()
                score = 0.5 + ctx_score
            else: continue
            if score > best_score:
                best_score = score; best_si = si
        if best_si >= 0 and best_score > 0.5:
            matched.append((gi, best_si))
            used_sys.add(best_si)
    return matched


# ============================================================
# 3. ID 매핑
# ============================================================

ID_MAP_A = {
    'kimcheomji': 'KC', 'wife': 'AW', 'gaeddong': 'GD',
    'student': 'HS', 'woman': 'FS', 'chisam': 'CS',
    'boy': 'JD', 'neighbor_lady': 'FS', 'teacher': 'HS',
    'bag_passenger': 'HS',
}

ID_MAP_C = {
    'kimcheomji': 'KC', 'wife': 'AW', 'gaeddong': 'GD',
    'student': 'HS', 'woman': 'FS', 'chisam': 'CS',
    'boy': 'JD', 'manim': 'FS', 'teacher': 'HS',
    'bagman': 'HS', 'passerby': '_EXTRA_',
}

def apply_id_map(mentions, id_map):
    for m in mentions:
        parts = m['ref'].split('_')
        mapped = [id_map.get(p, p) for p in parts if id_map.get(p, p) != '_EXTRA_']
        m['ref'] = '_'.join(mapped) if mapped else ''
    return [m for m in mentions if m['ref'] != '']

def build_clusters(mentions):
    clusters = defaultdict(set)
    for i, m in enumerate(mentions):
        clusters[m['ref']].add(i)
    return dict(clusters)


# ============================================================
# 4. CoNLL 메트릭 (MUC, B³, CEAFϕ4)
# ============================================================

def muc(gold_clusters, sys_clusters, mention_mapping):
    g_m2c = {}
    for cid, indices in gold_clusters.items():
        for idx in indices: g_m2c[idx] = cid
    s_m2c = {}
    for cid, indices in sys_clusters.items():
        for idx in indices: s_m2c[idx] = cid
    g2s_cluster = {}
    for gi, si in mention_mapping:
        if si in s_m2c: g2s_cluster[gi] = s_m2c[si]
    s2g_cluster = {}
    for gi, si in mention_mapping:
        if gi in g_m2c: s2g_cluster[si] = g_m2c[gi]
    recall_num = recall_den = 0
    for cid, indices in gold_clusters.items():
        indices = sorted(indices)
        if len(indices) <= 1: continue
        recall_den += len(indices) - 1
        sys_cids = set()
        for gi in indices:
            sys_cids.add(g2s_cluster.get(gi, f"_u_{gi}"))
        recall_num += len(indices) - len(sys_cids)
    prec_num = prec_den = 0
    for cid, indices in sys_clusters.items():
        indices = sorted(indices)
        if len(indices) <= 1: continue
        prec_den += len(indices) - 1
        gold_cids = set()
        for si in indices:
            gold_cids.add(s2g_cluster.get(si, f"_u_{si}"))
        prec_num += len(indices) - len(gold_cids)
    R = recall_num / recall_den if recall_den > 0 else 0
    P = prec_num / prec_den if prec_den > 0 else 0
    F = 2*P*R/(P+R) if (P+R) > 0 else 0
    return P, R, F

def b_cubed(gold_clusters, sys_clusters, mention_mapping):
    g_m2c = {}
    for cid, indices in gold_clusters.items():
        for idx in indices: g_m2c[idx] = cid
    s_m2c = {}
    for cid, indices in sys_clusters.items():
        for idx in indices: s_m2c[idx] = cid
    g2s = dict(mention_mapping)
    s2g = {si: gi for gi, si in mention_mapping}
    prec_sum = prec_count = recall_sum = recall_count = 0
    for gi, si in mention_mapping:
        g_cid = g_m2c[gi]; s_cid = s_m2c[si]
        g_cluster = gold_clusters[g_cid]; s_cluster = sys_clusters[s_cid]
        ov_r = sum(1 for gj in g_cluster if gj in g2s and g2s[gj] in s_cluster)
        ov_p = sum(1 for sj in s_cluster if sj in s2g and s2g[sj] in g_cluster)
        recall_sum += ov_r / len(g_cluster); recall_count += 1
        prec_sum += ov_p / len(s_cluster); prec_count += 1
    all_gold = set()
    for indices in gold_clusters.values(): all_gold |= indices
    for gi in all_gold - set(g2s.keys()):
        recall_count += 1
    all_sys = set()
    for indices in sys_clusters.values(): all_sys |= indices
    for si in all_sys - set(s2g.keys()):
        prec_count += 1
    R = recall_sum / recall_count if recall_count > 0 else 0
    P = prec_sum / prec_count if prec_count > 0 else 0
    F = 2*P*R/(P+R) if (P+R) > 0 else 0
    return P, R, F

def ceafe(gold_clusters, sys_clusters, mention_mapping):
    g2s = dict(mention_mapping)
    g_list = list(gold_clusters.items())
    s_list = list(sys_clusters.items())
    def phi4(g_idx, s_idx):
        ov = sum(1 for gi in g_idx if gi in g2s and g2s[gi] in s_idx)
        return 2 * ov / (len(g_idx) + len(s_idx)) if (len(g_idx) + len(s_idx)) > 0 else 0
    scores = []
    for i, (_, gi) in enumerate(g_list):
        for j, (_, sj) in enumerate(s_list):
            s = phi4(gi, sj)
            if s > 0: scores.append((s, i, j))
    scores.sort(reverse=True)
    used_g = set(); used_s = set(); total = 0
    for s, i, j in scores:
        if i not in used_g and j not in used_s:
            total += s; used_g.add(i); used_s.add(j)
    P = total / len(s_list) if s_list else 0
    R = total / len(g_list) if g_list else 0
    F = 2*P*R/(P+R) if (P+R) > 0 else 0
    return P, R, F


# ============================================================
# 5. 메인
# ============================================================

def main():
    gold_path = "/mnt/user-data/uploads/운수_좋은_날__1_.xml"
    files = {
        'A': ("/mnt/user-data/uploads/A-운수좋은날_coreference.xml", ID_MAP_A),
        'B': ("/mnt/user-data/uploads/B-운수_좋은_날_coreference.xml", None),
        'C': ("/mnt/user-data/uploads/C-운수좋은날_coreference.xml", ID_MAP_C),
        'D': ("/mnt/user-data/uploads/D-운수_좋은_날_coreference.xml", None),
    }
    
    gold_mentions, gold_text = extract_mentions_with_context(gold_path)
    gold_clusters = build_clusters(gold_mentions)
    
    print("=" * 70)
    print("  Span-based Coreference Evaluation")
    print(f"  Gold: {len(gold_mentions)} mentions, {len(gold_clusters)} clusters")
    print("=" * 70)
    
    results = {}
    for cond, (fpath, id_map) in files.items():
        sys_mentions, sys_text = extract_mentions_with_context(fpath)
        if id_map:
            sys_mentions = apply_id_map(sys_mentions, id_map)
        matched = match_mentions_by_context(gold_mentions, sys_mentions, gold_text, sys_text)
        sys_clusters = build_clusters(sys_mentions)
        
        # Matching accuracy
        correct = sum(1 for gi, si in matched if gold_mentions[gi]['ref'] == sys_mentions[si]['ref'])
        wrong = len(matched) - correct
        
        muc_p, muc_r, muc_f = muc(gold_clusters, sys_clusters, matched)
        b3_p, b3_r, b3_f = b_cubed(gold_clusters, sys_clusters, matched)
        ceaf_p, ceaf_r, ceaf_f = ceafe(gold_clusters, sys_clusters, matched)
        conll_f1 = (muc_f + b3_f + ceaf_f) / 3
        
        results[cond] = conll_f1
        
        print(f"\n  {cond}: sys={len(sys_mentions)}, matched={len(matched)}/{len(gold_mentions)}, "
              f"correct_ref={correct}, wrong_ref={wrong}")
        print(f"     MUC:    P={muc_p:.4f} R={muc_r:.4f} F1={muc_f:.4f}")
        print(f"     B3:     P={b3_p:.4f} R={b3_r:.4f} F1={b3_f:.4f}")
        print(f"     CEAFe:  P={ceaf_p:.4f} R={ceaf_r:.4f} F1={ceaf_f:.4f}")
        print(f"     CoNLL:  {conll_f1:.4f}")
    
    print(f"\n{'='*70}")
    print(f"  Ablation")
    print(f"{'='*70}")
    a,b,c,d = results['A'], results['B'], results['C'], results['D']
    print(f"  B-A = {b-a:+.4f}  C-A = {c-a:+.4f}  D-A = {d-a:+.4f}")
    print(f"  D-B = {d-b:+.4f}  D-C = {d-c:+.4f}")
    print(f"  B={b:.4f} vs C={c:.4f} → {'C>B' if c>b else 'B>C'}")

if __name__ == "__main__":
    main()
