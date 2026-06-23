"""
idml_to_md.py — IDMLの7 StoryをMarkdown（frontmatter付き）に抽出する

出力: ../extracted_md/story_XX_*.md (7ファイル)
Markdownに段落スタイル情報をコメントとして保持し、
md_to_xml.py で正確に戻せる形にする。

脚注: インライン記法 ^[脚注テキスト] を使用
"""
import zipfile, re, os, sys
from lxml import etree

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates', 'pmi_template.idml')
OUT_DIR  = os.path.join(os.path.dirname(__file__), '..', 'extracted_md')

STORY_TAGS = [
    ('story_00_prologue_ch01_rt01', 'u987',  'Stories/Story_u987.xml'),
    ('story_02_ch02_rt02',          'u10a9', 'Stories/Story_u10a9.xml'),
    ('story_03_ch03_rt03',          'u12fa', 'Stories/Story_u12fa.xml'),
    ('story_04_ch04_rt04',          'u154b', 'Stories/Story_u154b.xml'),
    ('story_05_ch05_rt05',          'u194b', 'Stories/Story_u194b.xml'),
    ('story_06_ch06_rt06',          'u1e63', 'Stories/Story_u1e63.xml'),
    ('story_07_epilogue_message',   'u2292', 'Stories/Story_u2292.xml'),
]

# 段落スタイル → Markdownプレフィックスのマッピング
STYLE_TO_MD = {
    '01-01 章 第◯章':    '# ',       # 章ラベル（プロローグ、第X章）
    '01-01 章 タイトル': '## ',      # 章タイトル
    '01-02 節 見出し':   '### ',     # 節見出し
    '01-03 小見出し':    '#### ',    # 小見出し
    '01 本文':           '',         # 本文（プレフィックスなし）
    '01-04 会話':        '',         # 会話（本文と同じ）
    '02 解説タイトル文': '<!-- ZADAN_TITLE --> ',  # 座談会タイトル
    '02 解説本文':       '<!-- ZADAN_BODY --> ',   # 座談会本文
    '02-01 座談会 問':   '<!-- ZADAN_Q --> ',      # 座談会 問
    '02-01 座談会 答':   '<!-- ZADAN_A --> ',      # 座談会 答
}


def extract_content_from_psr(psr):
    """ParagraphStyleRange から (style_name, text_with_footnotes) を返す"""
    style = psr.get('AppliedParagraphStyle', '').replace('ParagraphStyle/', '')
    # $ID/NormalParagraphStyle → スキップ
    if '$ID/' in style:
        return None

    parts = []
    for csr in psr.iter('CharacterStyleRange'):
        # 脚注処理
        for fn in csr.findall('Footnote'):
            fn_text = ''
            for fn_content in fn.iter('Content'):
                fn_text += (fn_content.text or '')
            parts.append(f'^[{fn_text}]')

        # 通常テキスト
        for content in csr.findall('Content'):
            if csr.find('Footnote') is None:  # 脚注内は除く
                t = content.text or ''
                # InDesign 改行 → 改行として保持
                t = t.replace('\r', '\n').replace('\x0d', '\n')
                parts.append(t)

        # Br → 段落内改行
        for br in csr.findall('Br'):
            parts.append('\n')

    text = ''.join(parts).strip()
    return (style, text)


def story_to_md(zf, story_path, tag_name):
    raw = zf.read(story_path).decode('utf-8')
    root = etree.fromstring(raw.encode('utf-8'))

    lines = []
    for psr in root.iter('ParagraphStyleRange'):
        result = extract_content_from_psr(psr)
        if result is None:
            continue
        style, text = result
        if not text and style not in ('01-01 章 第◯章', '01-01 章 タイトル'):
            continue

        prefix = STYLE_TO_MD.get(style, f'<!-- STYLE:{style} --> ')

        # 不明スタイルはコメント付きで保持（情報を落とさない）
        md_line = prefix + text
        lines.append((style, md_line))

    # 出力Markdown構築
    md_parts = []
    for style, line in lines:
        md_parts.append(line)

    return '\n\n'.join(md_parts)


def main():
    zf = zipfile.ZipFile(os.path.normpath(TEMPLATE))

    for tag_name, story_id, story_path in STORY_TAGS:
        print(f"extracting {tag_name}...", end=' ')
        try:
            md_body = story_to_md(zf, story_path, tag_name)
        except KeyError:
            print(f"SKIP (story not found)")
            continue

        frontmatter = f"""---
story_id: {tag_name}
story_file: {story_path}
replace_mode: content_only
---

"""
        out_path = os.path.join(OUT_DIR, f'{tag_name}.md')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter + md_body)
        print(f"→ {tag_name}.md ({len(md_body):,} chars)")

    zf.close()
    print("done")


if __name__ == '__main__':
    main()
