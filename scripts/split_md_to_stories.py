"""
split_md_to_stories.py — combined_body_only.md を 7 Story MDに分割して extracted_md/ へ出力

入力: E:\新刊 子会社売却のPMI\combined_body_only.md
      （または body_only.md で座談会なしも可）

出力: ../extracted_md/story_00_prologue_ch01_rt01.md
      ../extracted_md/story_02_ch02_rt02.md
      … (7ファイル)

段落スタイル判定:
  H1: # プロローグ...   → 章ラベル + タイトル分離
  H1: # ＜座談会N＞... → 座談会タイトル
  H2: ## N．xxx        → 節見出し
  短行（≤25文字、対話マーカーなし）→ 01-03 項 見出し (heuristic)
  "岡：" 等で始まる行  → 座談会 Q または A
  それ以外             → 01 本文

座談会は末尾に章番号付きで記載 → 対応する章ストーリーに末尾追記
"""
import re, os

SRC   = r'E:\新刊 子会社売却のPMI\combined_body_only.md'
OUT_D = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'extracted_md'))

# ストーリースロット定義
STORY_SLOTS = [
    ('story_00_prologue_ch01_rt01', 'u987',  ['プロローグ', '第１章']),
    ('story_02_ch02_rt02',          'u10a9', ['第２章']),
    ('story_03_ch03_rt03',          'u12fa', ['第３章']),
    ('story_04_ch04_rt04',          'u154b', ['第４章']),
    ('story_05_ch05_rt05',          'u194b', ['第５章']),
    ('story_06_ch06_rt06',          'u1e63', ['第６章']),
    ('story_07_epilogue_message',   'u2292', ['エピローグ', '＜メッセージ＞']),
]

ZADAN_MAP = {
    '１': 'story_00_prologue_ch01_rt01',
    '２': 'story_02_ch02_rt02',
    '３': 'story_03_ch03_rt03',
    '４': 'story_04_ch04_rt04',
    '５': 'story_05_ch05_rt05',
    '６': 'story_06_ch06_rt06',
}

# 座談会発言者 → Q/A スタイル（岡=質問者、それ以外=回答者）
FACILITATORS = {'岡'}


def classify_paragraph(text):
    """段落スタイルを判定して (style, text) を返す"""
    t = text.strip()
    if not t:
        return None, t

    # 座談会発言: 「岡：」「金田：」「ファシリテーター：」
    m = re.match(r'^([^\s：:]{1,10}[：:])(.*)$', t, re.DOTALL)
    if m:
        speaker = m.group(1).rstrip('：:').strip()
        content = m.group(2).strip()
        if speaker in FACILITATORS or speaker == 'ファシリテーター' or speaker == '岡':
            return '02-01 座談会 問', t
        else:
            return '02-01 座談会 答', t

    # 本文 vs 項見出し heuristic
    # 項見出し: ≤25文字、句読点なし（。、）、対話記号（「）なし
    is_short = len(t) <= 25
    no_punc = not re.search(r'[。、！？…]', t)
    no_dialog = not t.startswith('「') and not t.startswith('（')
    no_note = not t.startswith('注：') and not t.startswith('対談者')
    is_roman_item = bool(re.match(r'^[ⅰⅱⅲⅳⅰＡＢＣａｂｃ①②③]', t))

    if is_short and no_punc and no_dialog and no_note and not is_roman_item:
        return '01-03 項 見出し', t

    # 注釈・対談者情報 → 解説本文
    if t.startswith('注：') or t.startswith('対談者') or t.startswith('ファシリ'):
        return '02 解説本文', t

    return '01 本文', t


def parse_h1(line):
    """
    # プロローグ　タイトル  → ('プロローグ', 'タイトル')
    # 第N章　タイトル       → ('第N章', 'タイトル')
    # ＜座談会N＞　タイトル → ('ZADAN', 'N', 'タイトル')
    # エピローグ　タイトル  → ('エピローグ', 'タイトル')
    """
    t = line[2:].strip()  # remove '# '

    m = re.match(r'^＜座談会([１２３４５６])＞[　\s]*(.*)', t)
    if m:
        return ('ZADAN', m.group(1), m.group(2))

    m = re.match(r'^(プロローグ|エピローグ)[　\s]+(.*)', t)
    if m:
        return ('CHAP', m.group(1), m.group(2))

    m = re.match(r'^(第[１２３４５６]章)[　\s]+(.*)', t)
    if m:
        return ('CHAP', m.group(1), m.group(2))

    # メッセージ等
    m = re.match(r'^＜(.+?)＞[　\s]*(.*)', t)
    if m:
        return ('SPECIAL', m.group(1), m.group(2))

    return ('CHAP', '', t)


def slot_for_chapter(label):
    for tag, sid, labels in STORY_SLOTS:
        for l in labels:
            if l in label:
                return tag
    return None


def md_frontmatter(tag_name, story_file):
    return f"""---
story_id: {tag_name}
story_file: {story_file}
replace_mode: content_only
---

"""


def para_to_md_line(style, text):
    """(style, text) → Markdown行表現"""
    PREFIX = {
        '01-01 章 第◯章':     '# ',
        '01-01 章 タイトル':  '## ',
        '01-02 節 見出し':    '### ',
        '01-03 項 見出し':    '#### ',
        '02 解説タイトル文':  '<!-- ZADAN_TITLE --> ',
        '02 解説本文':        '<!-- ZADAN_BODY --> ',
        '02-01 座談会 問':    '<!-- Q --> ',
        '02-01 座談会 答':    '<!-- A --> ',
    }
    p = PREFIX.get(style, '')
    return p + text


def main():
    with open(SRC, encoding='utf-8') as f:
        raw = f.read()

    # frontmatter スキップ
    if raw.startswith('---'):
        end = raw.index('---', 3) + 3
        raw = raw[end:].lstrip('\n')

    lines = raw.split('\n')

    # ----- パス1: 章ブロックと座談会ブロックに分割 -----
    blocks = {}          # chapter_key → list of (style, text)
    zadan_blocks = {}    # '１' → list of (style, text)

    current_key = None
    current_is_zadan = False
    current_zadan_num = None
    current_block = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith('# '):
            # 現在のブロックを保存
            if current_key and current_block:
                if current_is_zadan:
                    zadan_blocks[current_zadan_num] = current_block
                else:
                    if current_key not in blocks:
                        blocks[current_key] = []
                    blocks[current_key].extend(current_block)

            h1 = parse_h1(line)
            if h1[0] == 'ZADAN':
                current_is_zadan = True
                current_zadan_num = h1[1]
                current_key = f'ZADAN_{h1[1]}'
                current_block = [('02 解説タイトル文', f'＜座談会{h1[1]}＞　{h1[2]}')]
            elif h1[0] in ('CHAP', 'SPECIAL'):
                current_is_zadan = False
                label = h1[1]
                title = h1[2]
                current_key = label or title[:10]
                current_block = []
                if label:
                    current_block.append(('01-01 章 第◯章', label))
                if title:
                    current_block.append(('01-01 章 タイトル', title))

        elif line.startswith('## '):
            text = line[3:].strip()
            current_block.append(('01-02 節 見出し', text))

        elif line.startswith('### '):
            text = line[4:].strip()
            current_block.append(('01-03 項 見出し', text))

        elif line.strip():
            # 複数行が `  ` (Markdown line break) で続く場合も1段落
            para = line.rstrip()
            # trailing 2-space continuation
            while (i + 1 < len(lines) and lines[i+1].endswith('  ')):
                i += 1
                para += '\n' + lines[i].rstrip()
            para = para.replace('  \n', '\n').strip()

            style, text = classify_paragraph(para)
            if style and text:
                current_block.append((style, text))

        i += 1

    # 最後のブロック
    if current_key and current_block:
        if current_is_zadan:
            zadan_blocks[current_zadan_num] = current_block
        else:
            if current_key not in blocks:
                blocks[current_key] = []
            blocks[current_key].extend(current_block)

    # ----- パス2: ストーリースロットに集約 + 座談会を末尾に追加 -----
    story_content = {tag: [] for tag, _, _ in STORY_SLOTS}

    for tag, sid, labels in STORY_SLOTS:
        for chapter_key, content in blocks.items():
            matched = any(l in chapter_key or chapter_key in l for l in labels)
            if matched:
                story_content[tag].extend(content)

    # 座談会を対応するストーリーに追記
    for znum, zcontent in zadan_blocks.items():
        target_tag = ZADAN_MAP.get(znum)
        if target_tag and target_tag in story_content:
            story_content[target_tag].extend(zcontent)
            print(f"  座談会{znum} → {target_tag}")

    # ----- パス3: Markdown出力 -----
    for tag, sid, labels in STORY_SLOTS:
        content = story_content[tag]
        if not content:
            print(f"  WARNING: {tag} is empty")
            continue

        story_file = f'Stories/Story_{sid}.xml'
        md_lines = []
        for style, text in content:
            md_lines.append(para_to_md_line(style, text))

        md_body = '\n\n'.join(md_lines)
        out_path = os.path.join(OUT_D, f'{tag}.md')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md_frontmatter(tag, story_file) + md_body)

        print(f"  {tag}.md: {len(content)} paragraphs")

    print("\ndone")


if __name__ == '__main__':
    main()
