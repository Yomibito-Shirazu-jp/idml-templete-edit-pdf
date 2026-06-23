# idml-templete-edit-pdf

InDesign IDML テンプレート変数置換パイプライン — 『子会社売却のPMI』組版

## 概要

前著（子会社売却入門）のInDesignデータをテンプレートとして、原稿だけをCSV変数で差し替えてIDMLを生成する。

```
templates/pmi_template_variables.idml  ← {{C_XXXXXX}} 入り固定テンプレート
idml_variable_map.csv                  ← 変数ID / スタイル / テキスト（text列のみ編集可）
scripts/fill_idml_from_csv.py          ← CSV → IDML 生成
output/pmi_filled.idml                 ← 生成物（gitignore）
```

## 使い方

### 原稿更新（毎回）

```powershell
cd scripts
python fill_idml_from_csv.py
```

`idml_variable_map.csv` の `text` 列を更新してから実行するだけ。

### テンプレート再生成（IDMLの構造を変えた場合のみ）

```powershell
python make_variable_template.py
```

## CSV 編集ルール

| 列 | 編集可否 |
|---|---|
| var_id | **禁止** |
| tag_name / story_id | **禁止** |
| psr_idx / psr_style | **禁止** |
| is_footnote | **禁止** |
| text | **ここだけ編集可** |
| permission | **禁止** |

## スクリプト一覧

| スクリプト | 用途 |
|---|---|
| `make_variable_template.py` | v3 IDML → テンプレート + CSV 生成（初回のみ） |
| `fill_idml_from_csv.py` | CSV → 完成IDML（毎回） |
| `split_md_to_stories.py` | Markdown原稿 → 7 Story MD分割 |
| `md_to_xml.py` | Story MD → InDesign XML |
| `inject_xml_to_idml.py` | XML × 7 → IDML（SimpleIDMLルート用） |
