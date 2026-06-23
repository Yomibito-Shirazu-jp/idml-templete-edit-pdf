"""
md_to_xml.py — extracted_md/*.md → xml/*.xml (InDesign Story XML形式)

frontmatterから story_id を読み取り、
Markdownの段落を InDesign ParagraphStyleRange/Content XML に変換する。

脚注: ^[テキスト] → <Footnote> 要素
"""
import re, os, glob
import xml.etree.ElementTree as ET

MD_DIR  = os.path.join(os.path.dirname(__file__), '..', 'extracted_md')
XML_DIR = os.path.join(os.path.dirname(__file__), '..', 'xml')

# Markdownプレフィックス → 段落スタイル名
MD_PREFIX_TO_STYLE = {
    '# ':                      '01-01 章 第◯章',
    '## ':                     '01-01 章 タイトル',
    '### ':                    '01-02 節 見出し',
    '#### ':                   '01-03 項 見出し',
    '<!-- ZADAN_TITLE --> ':   '02 解説タイトル文',
    '<!-- ZADAN_BODY --> ':    '02 解説本文',
    '<!-- Q --> ':             '02-01 座談会 問',
    '<!-- A --> ':             '02-01 座談会 答',
    '<!-- ZADAN_Q --> ':       '02-01 座談会 問',
    '<!-- ZADAN_A --> ':       '02-01 座談会 答',
}
BODY_STYLE = '01 本文'

_FOOTNOTE_ID = [0]  # mutable counter

def new_fn_id():
    _FOOTNOTE_ID[0] += 1
    return f'fn_{_FOOTNOTE_ID[0]:04d}'


def parse_frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip()
    body = text[m.end():]
    return fm, body


def detect_style(line):
    """行先頭プレフィックスからスタイルを判定"""
    for prefix, style in MD_PREFIX_TO_STYLE.items():
        if line.startswith(prefix):
            return style, line[len(prefix):]
    # コメント付き不明スタイル
    m = re.match(r'<!-- STYLE:(.*?) --> (.*)', line)
    if m:
        return m.group(1), m.group(2)
    return BODY_STYLE, line


def make_psr(style, text, is_last=False):
    """
    ParagraphStyleRange XML 文字列を生成（lxmlを使わず文字列テンプレートで）
    段落内の脚注 ^[...] をインライン Footnote に変換する
    """
    segments = split_footnotes(text)

    csr_parts = []
    for seg_type, seg_text in segments:
        if seg_type == 'text':
            # InDesign 改行はそのまま Content に
            escaped = xml_escape(seg_text)
            csr_parts.append(
                f'<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">'
                f'<Content>{escaped}</Content>'
                f'</CharacterStyleRange>'
            )
        elif seg_type == 'fn':
            fn_id = new_fn_id()
            fn_text = xml_escape(seg_text)
            csr_parts.append(
                f'<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">'
                f'<Footnote>'
                f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/01-05 脚注">'
                f'<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">'
                f'<Content>{fn_text}</Content>'
                f'</CharacterStyleRange>'
                f'</ParagraphStyleRange>'
                f'</Footnote>'
                f'</CharacterStyleRange>'
            )

    # 段落末尾の Br（最後の段落以外）は InDesign の段落区切りに対応
    br = '' if is_last else ''  # ParagraphStyleRange の連続で段落を表現するため Br は不要
    style_escaped = xml_escape(f'ParagraphStyle/{style}')
    return (
        f'<ParagraphStyleRange AppliedParagraphStyle="{style_escaped}">'
        + ''.join(csr_parts) +
        f'</ParagraphStyleRange>'
    )


def split_footnotes(text):
    """テキストを通常テキストと脚注 ^[...] に分割"""
    parts = []
    pattern = re.compile(r'\^\[(.*?)\]', re.DOTALL)
    last = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            parts.append(('text', text[last:m.start()]))
        parts.append(('fn', m.group(1)))
        last = m.end()
    if last < len(text):
        parts.append(('text', text[last:]))
    return parts


def xml_escape(s):
    return (s.replace('&', '&amp;')
              .replace('<', '&lt;')
              .replace('>', '&gt;')
              .replace('"', '&quot;'))


def md_to_story_xml(md_text, tag_name, story_file):
    """MDテキスト → Story XML文字列"""
    fm, body = parse_frontmatter(md_text)
    tag = fm.get('story_id', tag_name)

    # 空行で段落分割
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', body) if p.strip()]

    psrs = []
    for i, para in enumerate(paragraphs):
        style, text = detect_style(para)
        # 段落内改行を保持（InDesign では Content 内の \n がソフト改行）
        psrs.append(make_psr(style, text, is_last=(i == len(paragraphs)-1)))

    # 空の場合でも最低1段落
    if not psrs:
        psrs.append(make_psr('$ID/NormalParagraphStyle', ''))

    inner_xml = '\n'.join(psrs)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.0">
<XMLElement Self="{tag_name}_xe" MarkupTag="XMLTag/{tag_name}">
{inner_xml}
</XMLElement>
</idPkg:Story>
"""


def main():
    md_files = sorted(glob.glob(os.path.join(MD_DIR, '*.md')))
    if not md_files:
        print("No .md files found in extracted_md/")
        return

    for md_path in md_files:
        tag_name = os.path.splitext(os.path.basename(md_path))[0]
        print(f"converting {tag_name}...", end=' ')

        with open(md_path, encoding='utf-8') as f:
            md_text = f.read()

        fm, _ = parse_frontmatter(md_text)
        story_file = fm.get('story_file', f'Stories/Story_{tag_name}.xml')

        xml_text = md_to_story_xml(md_text, tag_name, story_file)
        out_path = os.path.join(XML_DIR, f'{tag_name}.xml')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(xml_text)
        print(f"→ {tag_name}.xml")

    print("done")


if __name__ == '__main__':
    main()
