"""
docx_to_idml.py — docx 2本 + IDMLテンプレート → IDML 生成 (全パイプライン)

使用例:
  python scripts/docx_to_idml.py
    --honbun  "data/子会社売却のPMI.docx"
    --zadan   "data/座談会 原稿.docx"
    --template templates/pmi_template.idml
    --output  output/pmi_built.idml
"""
import argparse, zipfile, shutil, os, re, json
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NUM = re.compile(r'^([　 ]*)([０-９0-9]+)[．.]\s*(.*)$')
FW  = str.maketrans('0123456789', '０１２３４５６７８９')


# ── docx 読み込み ──────────────────────────────────────────────
def load_doc(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read('word/document.xml').decode('utf-8'))
    body = root.find(f'{W}body')
    fns = {}
    try:
        fr = ET.fromstring(z.read('word/footnotes.xml').decode('utf-8'))
        for fn in fr.findall(f'{W}footnote'):
            fid = fn.get(f'{W}id')
            txt = ''.join(t.text or '' for t in fn.iter(f'{W}t')).strip()
            if fid not in ('-1', '0') and txt:
                fns[fid] = txt
    except KeyError:
        pass
    paras = []
    for p in body.findall(f'{W}p'):
        ppr = p.find(f'{W}pPr'); psz = None; align = None
        if ppr is not None:
            jc = ppr.find(f'{W}jc')
            align = jc.get(f'{W}val') if jc is not None else None
            rpr = ppr.find(f'{W}rPr')
            if rpr is not None:
                s = rpr.find(f'{W}sz')
                psz = s.get(f'{W}val') if s is not None else None
        seq = []; rsz = None; rbold = False
        for r in p.findall(f'{W}r'):
            rp = r.find(f'{W}rPr')
            if rp is not None:
                s = rp.find(f'{W}sz')
                if s is not None and rsz is None:
                    rsz = s.get(f'{W}val')
                if rp.find(f'{W}b') is not None:
                    rbold = True
            for ch in r:
                tag = ch.tag.split('}')[-1]
                if tag == 't':
                    seq.append(('t', ch.text or ''))
                elif tag == 'footnoteReference':
                    seq.append(('fn', ch.get(f'{W}id')))
                elif tag == 'tab':
                    seq.append(('t', '\t'))
                elif tag == 'br':
                    seq.append(('t', '\n'))
        text = ''.join(x[1] for x in seq if x[0] == 't')
        paras.append({'sz': psz or rsz, 'bold': rbold, 'align': align,
                      'seq': seq, 'text': text})
    return paras, fns


# ── 段落分類 ───────────────────────────────────────────────────
def classify_body(p):
    sz = p['sz']; t = p['text'].strip(); bold = p['bold']
    if not t: return None
    CHAP_PAT = re.compile(r'^(第[０-９0-9]+章|プロローグ|エピローグ)[　 ]*(.*)')
    if sz == '28':
        m = CHAP_PAT.match(t.strip())
        if m: return ('CHAP', m.group(1), m.group(2))
        if t.strip() in ('プロローグ', 'エピローグ'):
            return ('CHAP', t.strip(), '')
        return ('CHAP', None, t.strip())
    if sz == '24':
        if t.startswith('プロローグ') or t.startswith('エピローグ'):
            m = CHAP_PAT.match(t)
            return ('CHAP', m.group(1), m.group(2)) if m else ('CHAP', None, t)
        mm = NUM.match(t)
        if mm: return ('SEC', mm.group(2).translate(FW), mm.group(3))
        if t.startswith('「') or t.startswith('『'): return ('BODY',)
        return ('KOU',)
    if sz == '22':
        return ('KOU',) if bold else ('BODY',)
    return ('BODY',)


def classify_zad(p):
    sz = p['sz']; t = p['text'].strip()
    if not t: return None
    if t.startswith('＜座談会') or t.startswith('＜メッセージ'): return ('ZTITLE', t)
    mm = NUM.match(t)
    if mm and sz == '24': return ('ZSEC', mm.group(2).translate(FW), mm.group(3))
    if t.startswith('■'): return ('ZSUB',)
    return ('ZBODY',)


def conv_seq(seq, fnmap):
    out = []
    for kind, val in seq:
        if kind == 't':
            if val: out.append(['t', val])
        else:
            out.append(['fn', fnmap.get(val, '')])
    return out


# ── IDML XML 生成 ──────────────────────────────────────────────
CS_NONE = 'CharacterStyle/$ID/[No character style]'
CS_FN   = 'CharacterStyle/文中 脚注マーカ'


def esc(t):
    return (t.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))


def fw_line(t):
    return t.replace('\r\n', '\n').replace('\n', ' ').replace('\t', ' ')


def footnote_xml(text):
    t = esc(fw_line(text))
    return (f'<Footnote>'
            f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/01-05 脚注">'
            f'<CharacterStyleRange AppliedCharacterStyle="{CS_NONE}"><Content><?ACE 4?></Content></CharacterStyleRange>'
            f'<CharacterStyleRange AppliedCharacterStyle="{CS_NONE}"><Content>　{t}</Content></CharacterStyleRange>'
            f'</ParagraphStyleRange></Footnote>')


def para_xml(style, seq):
    parts = []; buf = []
    def flush():
        if buf:
            txt = esc(fw_line(''.join(buf)))
            parts.append(f'<CharacterStyleRange AppliedCharacterStyle="{CS_NONE}"><Content>{txt}</Content></CharacterStyleRange>')
            buf.clear()
    for kind, val in seq:
        if kind == 't':
            buf.append(val)
        else:
            flush()
            parts.append(f'<CharacterStyleRange AppliedCharacterStyle="{CS_FN}">{footnote_xml(val)}</CharacterStyleRange>')
    flush()
    if not parts:
        parts.append(f'<CharacterStyleRange AppliedCharacterStyle="{CS_NONE}"><Content></Content></CharacterStyleRange>')
    last = parts[-1]
    parts[-1] = last[:-len('</CharacterStyleRange>')] + '<Br />' + '</CharacterStyleRange>'
    return f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/{style}">' + ''.join(parts) + '</ParagraphStyleRange>'


def replace_story_body(story_path, new_psr):
    raw = open(story_path, encoding='utf-8').read()
    i = raw.find('<ParagraphStyleRange')
    if i < 0:
        j = raw.rfind('</Story>')
        prefix = raw[:j]; suffix = raw[j:]
    else:
        j = raw.rfind('</ParagraphStyleRange>') + len('</ParagraphStyleRange>')
        prefix = raw[:i]; suffix = raw[j:]
    # XMLElement ラッパーを保持
    xe_start = prefix.rfind('<XMLElement ')
    if xe_start >= 0:
        prefix = prefix[:xe_start + prefix[xe_start:].index('>') + 1] + '\n'
    open(story_path, 'w', encoding='utf-8').write(prefix + new_psr + suffix)


# ── メイン ────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--honbun',   required=True)
    p.add_argument('--zadan',    required=True)
    p.add_argument('--template', required=True)
    p.add_argument('--output',   required=True)
    args = p.parse_args()

    print("loading docx...")
    honbun, hfn = load_doc(args.honbun)
    zad, zfn    = load_doc(args.zadan)
    print(f"  honbun: {len(honbun)} paras, {len(hfn)} footnotes")
    print(f"  zadan:  {len(zad)} paras,  {len(zfn)} footnotes")

    # ── body chapters ──
    chapters = []; cur = None
    for i, pp in enumerate(honbun):
        if i < 190: continue
        c = classify_body(pp)
        if c is None: continue
        if c[0] == 'CHAP':
            cur = {'label': c[1], 'title': c[2], 'items': []}
            chapters.append(cur); continue
        if cur is None:
            cur = {'label': None, 'title': '(冒頭)', 'items': []}
            chapters.append(cur)
        if c[0] == 'SEC':
            cur['items'].append({'style': '01-02 節 数字',  'seq': [['t', c[1]]]})
            cur['items'].append({'style': '01-02 節 見出し', 'seq': [['t', c[2]]]})
        elif c[0] == 'KOU':
            cur['items'].append({'style': '01-04 ■小見出し', 'seq': conv_seq(pp['seq'], hfn)})
        else:
            cur['items'].append({'style': '01 本文', 'seq': conv_seq(pp['seq'], hfn)})

    # ── 座談会 ──
    zad_sections = []; zc = None
    for pp in zad:
        c = classify_zad(pp)
        if c is None: continue
        if c[0] == 'ZTITLE':
            zc = {'title': c[1], 'items': [{'style': '02 解説タイトル文', 'seq': [['t', c[1]]]}]}
            zad_sections.append(zc)
        else:
            if zc is None:
                zc = {'title': '(座談)', 'items': []}; zad_sections.append(zc)
            if c[0] == 'ZSEC':
                zc['items'].append({'style': '02-01 解説見出し', 'seq': [['t', f"{c[1]}．{c[2]}"]]})
            elif c[0] == 'ZSUB':
                zc['items'].append({'style': '02-02 解説■小見出し', 'seq': conv_seq(pp['seq'], zfn)})
            else:
                zc['items'].append({'style': '02-02 解説 本文', 'seq': conv_seq(pp['seq'], zfn)})

    # ── interleave ──
    final = []; zad_idx = 0
    for ch in chapters:
        block = {'label': ch['label'], 'title': ch['title'], 'items': list(ch['items'])}
        if ch['label'] and ch['label'].startswith('第') and zad_idx < len(zad_sections):
            block['items'].extend(zad_sections[zad_idx]['items']); zad_idx += 1
        final.append(block)

    print(f"chapters: {[(c['label'], c['title'][:15]) for c in final]}")

    # ── IDML 組み立て ──
    WORK = os.path.join(os.path.dirname(args.output), '_build_work')
    if os.path.exists(WORK): shutil.rmtree(WORK)
    zipfile.ZipFile(args.template).extractall(WORK)

    # body story → chapter indices
    ASSIGN = {
        'u987':  [0, 1], 'u10a9': [2], 'u12fa': [3],
        'u154b': [4], 'u194b': [5], 'u1e63': [6], 'u2292': [7],
    }
    # chapter index → (章番号 story, 章タイトル story)
    # prologue (idx=0) has no dedicated heading frame; ch1-epilogue do
    HEADING_ASSIGN = {
        1: ('u955',  'u970'),
        2: ('u1076', 'u1092'),
        3: ('u12c9', 'u12e3'),
        4: ('u151a', 'u1534'),
        5: ('u191a', 'u1934'),
        6: ('u1e32', 'u1e4c'),
        7: ('u2261', 'u227b'),
    }

    for sid, idxs in ASSIGN.items():
        items = []
        for k in idxs:
            ch = final[k]
            if k == 0:
                # prologue has no dedicated heading frame; embed inline
                if ch['label']:
                    items.append({'style': '01-01 章 第◯章', 'seq': [['t', ch['label']]]})
                items.append({'style': '01-01 章 タイトル', 'seq': [['t', ch['title']]]})
            # chapters 1-7: heading goes to dedicated stories; only body here
            items.extend(ch['items'])
        psr = '\n'.join(para_xml(it['style'], it['seq']) for it in items)
        replace_story_body(os.path.join(WORK, 'Stories', f'Story_{sid}.xml'), psr)
        print(f"  {sid}: {len(items)} paragraphs")

    # write dedicated chapter heading stories
    HEADING_EMPTY = (
        f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/$ID/NormalParagraphStyle">'
        f'<CharacterStyleRange AppliedCharacterStyle="{CS_NONE}"><Br /></CharacterStyleRange></ParagraphStyleRange>'
    )
    for ch_idx, (label_sid, title_sid) in HEADING_ASSIGN.items():
        ch = final[ch_idx]
        label = ch['label'] or ch['title']
        replace_story_body(
            os.path.join(WORK, 'Stories', f'Story_{label_sid}.xml'),
            para_xml('01-01 章 第◯章', [['t', label]])
        )
        replace_story_body(
            os.path.join(WORK, 'Stories', f'Story_{title_sid}.xml'),
            para_xml('01-01 章 タイトル', [['t', ch['title']]])
        )
        print(f"  heading {ch_idx}: {label_sid}={label!r:.20} / {title_sid}={ch['title']!r:.20}")

    # empty remaining heading/section stories (section-start frames)
    EMPTY = HEADING_EMPTY
    for sid in ['u10c5','u1316','u1567','u1967','u1e7f','u22ae','u259a',
                'u2e92','u2fb2','u2fe8','u301e','u3053','u326a','u32a0',
                'u32df','u3315','u3350','u3576','u35c5','u3603','u36c5',
                'uca5','ud7b','u10dc','u132d','u157e','u197e','u1e96',
                'u22c5','u25b1','u2ea9','u2fc9','u3000','u3035','u306b',
                'u3281','u32b8','u32f6','u332c','u3367','u358d','u35dd',
                'u361a','u36dc','ucbc','ud92']:
        sp = os.path.join(WORK, 'Stories', f'Story_{sid}.xml')
        if os.path.exists(sp):
            replace_story_body(sp, EMPTY)

    # package
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    if os.path.exists(args.output): os.remove(args.output)
    all_files = []
    for rd, _, fs in os.walk(WORK):
        for fn in fs:
            full = os.path.join(rd, fn)
            rel  = os.path.relpath(full, WORK).replace(os.sep, '/')
            all_files.append((rel, full))
    all_files.sort(key=lambda x: (x[0] != 'mimetype', x[0]))
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as zout:
        zout.write(all_files[0][1], 'mimetype', compress_type=zipfile.ZIP_STORED)
        for rel, full in all_files[1:]:
            zout.write(full, rel)
    shutil.rmtree(WORK)
    print(f"wrote {args.output}  ({os.path.getsize(args.output):,} bytes)")


if __name__ == '__main__':
    main()
