"""
update_csv_from_stories.py

extracted_md/*.md (v5版) と idml_variable_map.csv を照合し、
変更のある text 行だけ上書きして idml_variable_map.csv を更新する。

前提:
  - 段落の数・順序は変わっていない (構造変更なし)
  - 変更は text の中身だけ（誤字修正等）
  - is_footnote=True 行はスキップ（脚注は別途管理）

出力:
  - idml_variable_map.csv  (上書き保存)
  - update_report.txt      (差分レポート)
"""
import csv, os, re, difflib

BASE    = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
MD_DIR  = os.path.join(BASE, 'extracted_md')
CSV_IN  = os.path.join(BASE, 'idml_variable_map.csv')
REPORT  = os.path.join(BASE, 'update_report.txt')

STORY_ORDER = [
    ('story_00_prologue_ch01_rt01', 'u987'),
    ('story_02_ch02_rt02',          'u10a9'),
    ('story_03_ch03_rt03',          'u12fa'),
    ('story_04_ch04_rt04',          'u154b'),
    ('story_05_ch05_rt05',          'u194b'),
    ('story_06_ch06_rt06',          'u1e63'),
    ('story_07_epilogue_message',   'u2292'),
]

MD_PREFIX_TO_STYLE = {
    '# ':                      '01-01 章 第◯章',
    '## ':                     '01-01 章 タイトル',
    '### ':                    '01-02 節 見出し',
    '#### ':                   '01-03 項 見出し',
    '<!-- ZADAN_TITLE --> ':   '02 解説タイトル文',
    '<!-- ZADAN_BODY --> ':    '02 解説本文',
    '<!-- Q --> ':             '02-01 座談会 問',
    '<!-- A --> ':             '02-01 座談会 答',
}


def parse_md_paragraphs(md_path):
    """MDファイルから段落テキストのリストを返す（frontmatterスキップ、style付き）"""
    with open(md_path, encoding='utf-8') as f:
        text = f.read()
    # frontmatter スキップ
    if text.startswith('---'):
        end = text.index('---', 3) + 3
        text = text[end:].lstrip('\n')

    paras = []
    for block in re.split(r'\n{2,}', text):
        block = block.strip()
        if not block:
            continue
        # プレフィックスでスタイル検出
        style = '01 本文'
        content = block
        for prefix, s in MD_PREFIX_TO_STYLE.items():
            if block.startswith(prefix):
                style = s
                content = block[len(prefix):]
                break
        paras.append((style, content))
    return paras


def main():
    # CSV ロード
    rows = []
    with open(CSV_IN, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(dict(row))

    # story ごとに CSV 行インデックスを収集（is_footnote=False のみ）
    story_rows = {}
    for tag_name, _ in STORY_ORDER:
        story_rows[tag_name] = [
            i for i, r in enumerate(rows)
            if r['tag_name'] == tag_name and r['is_footnote'] == 'False'
        ]

    report_lines = []
    changed_count = 0
    errors = []

    for tag_name, story_id in STORY_ORDER:
        md_path = os.path.join(MD_DIR, f'{tag_name}.md')
        if not os.path.exists(md_path):
            errors.append(f"SKIP {tag_name}: MD not found")
            continue

        md_paras = parse_md_paragraphs(md_path)
        csv_idxs = story_rows[tag_name]

        # 段落数チェック
        if len(md_paras) != len(csv_idxs):
            errors.append(
                f"MISMATCH {tag_name}: MD={len(md_paras)} paras, CSV={len(csv_idxs)} rows"
            )
            # 数が合わない場合は最小値まで処理
            count = min(len(md_paras), len(csv_idxs))
        else:
            count = len(md_paras)

        story_changes = 0
        for i in range(count):
            csv_idx = csv_idxs[i]
            row = rows[csv_idx]
            new_style, new_text = md_paras[i]
            old_text = row['text']

            if old_text != new_text:
                # difflib で差分を可視化
                diff = list(difflib.ndiff([old_text], [new_text]))
                report_lines.append(f"[{tag_name}] row {csv_idx} (var {row['var_id']}):")
                for d in diff:
                    if d.startswith('- ') or d.startswith('+ '):
                        report_lines.append(f"  {d}")
                report_lines.append('')

                rows[csv_idx]['text'] = new_text
                story_changes += 1
                changed_count += 1

        print(f"  {tag_name}: {story_changes} changes")

    # CSV 書き戻し
    with open(CSV_IN, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # レポート書き出し
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write(f"=== v5 差分レポート ===\n")
        f.write(f"変更行数: {changed_count}\n\n")
        if errors:
            f.write("=== 警告 ===\n")
            for e in errors:
                f.write(f"  {e}\n")
            f.write('\n')
        if report_lines:
            f.write("=== 差分詳細 ===\n")
            f.write('\n'.join(report_lines))
        else:
            f.write("差分なし\n")

    print(f"\n合計 {changed_count} 行更新 → {CSV_IN}")
    print(f"レポート: {REPORT}")
    if errors:
        for e in errors:
            print(f"  WARNING: {e}")


if __name__ == '__main__':
    main()
